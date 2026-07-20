#!/usr/bin/env python3
"""Safely copy KIE settings from a private env file into onion-ad runtime config."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile


SYNC_KEYS = ("KIE_API_KEY", "KIE_BASE_URL", "KIE_UPLOAD_BASE_URL")
DEFAULTS = {
    "KIE_BASE_URL": "https://api.kie.ai",
    "KIE_UPLOAD_BASE_URL": "https://kieai.redpandaai.co",
}
PLACEHOLDER_MARKERS = ("你的", "占位", "your-key", "sk-xxx")


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def is_placeholder(value: str) -> bool:
    lowered = str(value or "").strip().lower()
    return not lowered or any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def merged_lines(existing: str, replacements: dict[str, str]) -> str:
    output: list[str] = []
    replaced: set[str] = set()
    for raw in existing.splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in replacements:
                if key not in replaced:
                    output.append(f"{key}={replacements[key]}")
                    replaced.add(key)
                continue
        output.append(raw)
    missing = [key for key in SYNC_KEYS if key not in replaced]
    if missing:
        if output and output[-1].strip():
            output.append("")
        output.append("# ===== KIE API（由 migrate_kie_config.py 安全同步）=====")
        output.extend(f"{key}={replacements[key]}" for key in missing)
    return "\n".join(output).rstrip() + "\n"


def migrate(source: Path, target: Path) -> dict[str, object]:
    source = source.expanduser().resolve()
    target = target.expanduser().resolve()
    values = parse_env(source)
    api_key = values.get("KIE_API_KEY", "")
    if is_placeholder(api_key):
        raise ValueError("source KIE_API_KEY is missing or a placeholder")
    replacements = {
        "KIE_API_KEY": api_key,
        "KIE_BASE_URL": values.get("KIE_BASE_URL") or DEFAULTS["KIE_BASE_URL"],
        "KIE_UPLOAD_BASE_URL": values.get("KIE_UPLOAD_BASE_URL") or DEFAULTS["KIE_UPLOAD_BASE_URL"],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    backup: Path | None = None
    mode = 0o600
    if target.is_file():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = target.with_name(f"{target.name}.backup-{timestamp}")
        shutil.copy2(target, backup)
        mode = target.stat().st_mode & 0o777
    content = merged_lines(existing, replacements)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode or 0o600)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return {
        "ok": True,
        "source": str(source),
        "target": str(target),
        "backup": str(backup) if backup else None,
        "synced_keys": list(SYNC_KEYS),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Private source .env file")
    parser.add_argument("--target", default=str(Path.home() / ".onion-ad" / ".env"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = migrate(Path(args.source), Path(args.target))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
