from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_TOKEN = "WIoGb0ksnaREvJsPtQCcW8Lsnfg"


def load_env() -> None:
    for path in (Path.home() / ".onion-ad" / ".env", Path.cwd() / ".env", PLUGIN_ROOT / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def base_token(explicit: Optional[str] = None) -> str:
    load_env()
    return explicit or os.environ.get("ONION_BASE_APP_TOKEN") or DEFAULT_BASE_TOKEN


def lark_bin() -> str:
    load_env()
    return os.environ.get("LARK_CLI_BIN") or "lark-cli"


def pending_path() -> Path:
    return Path.home() / ".onion-ad" / "pending.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def make_hash(*parts: Any) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(stable_json(part).encode("utf-8"))
    return "sha256:" + digest.hexdigest()


def operation_name(op_type: str) -> str:
    if op_type == "record_batch_create":
        return "+record-batch-create"
    if op_type == "record_batch_update":
        return "+record-batch-update"
    if op_type == "attachment_upload":
        return "+record-upload-attachment"
    raise ValueError(f"Unsupported operation type: {op_type}")


def build_command(op_type: str, payload: Dict[str, Any], dry_run: bool = False) -> List[str]:
    command = [
        lark_bin(),
        "base",
        operation_name(op_type),
        "--base-token",
        payload["base_token"],
        "--table-id",
        payload["table_id"],
        "--as",
        payload.get("as_identity", "user"),
    ]
    if op_type in {"record_batch_create", "record_batch_update"}:
        command.extend(["--json", json.dumps(payload["lark_payload"], ensure_ascii=False)])
    else:
        for flag, key in (
            ("--record-id", "record_id"),
            ("--field-id", "field_id"),
            ("--file", "file"),
            ("--name", "name"),
        ):
            value = payload.get(key)
            if value:
                command.extend([flag, str(value)])
    if dry_run:
        command.append("--dry-run")
    return command


def dry_run_response(op_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "operation": op_type,
        "dry_run": True,
        "table_id": payload["table_id"],
        "lark_payload": payload.get("lark_payload"),
        "command": build_command(op_type, payload, dry_run=True),
    }


def classify_retry(error_text: str) -> Tuple[bool, bool]:
    lowered = error_text.lower()
    retryable_markers = ("429", "rate limit", "timeout", "temporarily", " 5", "5xx", "server error")
    auth_markers = ("401", "403", "permission", "unauthorized", "forbidden")
    if any(marker in lowered for marker in auth_markers):
        return False, False
    if any(marker in lowered for marker in retryable_markers):
        return True, False
    return True, False


def make_pending_item(
    op_type: str,
    payload: Dict[str, Any],
    error_text: str,
    retry_count: int = 0,
    max_retries: int = 3,
    ambiguous: bool = False,
) -> Dict[str, Any]:
    retryable, default_ambiguous = classify_retry(error_text)
    ambiguous = ambiguous or default_ambiguous
    stamp = now_iso()
    idempotency_key = make_hash(op_type, payload)
    op_id_seed = f"{stamp}-{idempotency_key}"
    return {
        "schema_version": 1,
        "op_id": hashlib.sha1(op_id_seed.encode("utf-8")).hexdigest()[:16],
        "op_type": op_type,
        "idempotency_key": idempotency_key,
        "payload": payload,
        "retry_count": retry_count,
        "max_retries": max_retries,
        "retryable": retryable,
        "ambiguous": ambiguous,
        "last_error": error_text,
        "created_at": stamp,
        "updated_at": stamp,
    }


def append_pending(item: Dict[str, Any], path: Optional[Path] = None) -> None:
    path = path or pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def read_pending(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = path or pending_path()
    if not path.exists():
        return []
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


def write_pending(items: Iterable[Dict[str, Any]], path: Optional[Path] = None) -> None:
    path = path or pending_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    materialized = list(items)
    if not materialized:
        if path.exists():
            path.unlink()
        return
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in materialized),
        encoding="utf-8",
    )


def parse_record_ids(stdout: str) -> List[str]:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    current = data.get("data", data)
    if isinstance(current, dict):
        for key in ("record_id_list", "record_ids"):
            value = current.get(key)
            if isinstance(value, list):
                return [str(item) for item in value]
        records = current.get("records")
        if isinstance(records, list):
            ids = []
            for record in records:
                if isinstance(record, dict) and record.get("record_id"):
                    ids.append(str(record["record_id"]))
            return ids
    return []


def execute(op_type: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
    command = build_command(op_type, payload, dry_run=False)
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode == 0:
        return (
            True,
            {
                "ok": True,
                "operation": op_type,
                "record_ids": parse_record_ids(result.stdout),
                "dry_run": False,
            },
            "",
        )
    return False, {}, (result.stderr or result.stdout or f"exit code {result.returncode}").strip()


def execute_with_retry_or_pending(
    op_type: str,
    payload: Dict[str, Any],
    max_retries: int = 3,
) -> Tuple[int, Dict[str, Any]]:
    last_error = ""
    for attempt in range(max_retries):
        ok, response, error = execute(op_type, payload)
        if ok:
            return 0, response
        last_error = error
        retryable, _ = classify_retry(last_error)
        if not retryable or attempt == max_retries - 1:
            break
        time.sleep([1, 3, 9][min(attempt, 2)])
    item = make_pending_item(op_type, payload, last_error, max_retries=max_retries)
    append_pending(item)
    return 5, {"ok": False, "queued": True, "pending_op_id": item["op_id"], "error": last_error}


def retry_items(force_ambiguous: bool = False, path: Optional[Path] = None) -> Dict[str, int]:
    items = read_pending(path)
    remaining = []
    stats = {"processed": len(items), "succeeded": 0, "still_failing": 0, "ambiguous_skipped": 0}
    for item in items:
        if item.get("ambiguous") and not force_ambiguous:
            stats["ambiguous_skipped"] += 1
            remaining.append(item)
            continue
        if not item.get("retryable", False) or item.get("retry_count", 0) >= item.get("max_retries", 3):
            stats["still_failing"] += 1
            remaining.append(item)
            continue
        ok, _, error = execute(item["op_type"], item["payload"])
        if ok:
            stats["succeeded"] += 1
            continue
        item["retry_count"] = int(item.get("retry_count", 0)) + 1
        item["last_error"] = error
        item["updated_at"] = now_iso()
        stats["still_failing"] += 1
        remaining.append(item)
    write_pending(remaining, path)
    return stats
