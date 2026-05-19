from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import base_ops
from runtime_paths import output_root
from write_record import build_lark_payload


DEFAULT_IMAGE_GROUPS_TABLE_ID = "tblGpuukciptN3PP"
DEFAULT_TARGET_KB = 200
CONTROL_METADATA_KEYS = {"target_kb", "目标KB", "压缩目标KB", "文件大小KB"}
IMAGE_COMPRESS_SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "onion-image" / "scripts" / "image_compress.py"
IMAGE_CLEANUP_SCRIPT = Path(__file__).resolve().parents[2] / "skills" / "onion-image" / "scripts" / "cleanup_image_outputs.py"


def normalize_parent(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if value.lower() in {"", "null", "none"}:
        return None
    return value


def normalize_images(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("--images must be a non-empty JSON array")

    normalized: List[Dict[str, Any]] = []
    for position, item in enumerate(value, start=1):
        if isinstance(item, str):
            normalized.append({"index": position, "path": item})
            continue
        if not isinstance(item, dict):
            raise ValueError("--images entries must be file paths or objects")
        if "path" not in item:
            raise ValueError("--images object entries must include path")
        image = dict(item)
        image.setdefault("index", position)
        normalized.append(image)
    return normalized


def parse_target_kb(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        target = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"target KB must be an integer, got {value!r}") from exc
    if target <= 0:
        raise ValueError("target KB must be positive")
    return target


def resolve_default_target_kb(explicit: Optional[int], metadata: Dict[str, Any]) -> int:
    if explicit is not None:
        return explicit
    for key in CONTROL_METADATA_KEYS:
        target = parse_target_kb(metadata.get(key))
        if target is not None:
            return target
    env_target = parse_target_kb(os.environ.get("IMAGE_COMPRESS_TARGET_KB"))
    return env_target or DEFAULT_TARGET_KB


def strip_control_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in metadata.items() if key not in CONTROL_METADATA_KEYS}


def compressed_path_for(source: str, target_kb: int, target_width: Optional[int] = None, target_height: Optional[int] = None) -> str:
    path = Path(source)
    size_suffix = f".{target_width}x{target_height}" if target_width and target_height else ""
    return str(path.with_name(f"{path.stem}{size_suffix}.compressed-{target_kb}kb.jpg"))


def build_compression_plan(images: List[Dict[str, Any]], default_target_kb: int, compress: bool) -> List[Dict[str, Any]]:
    if not compress:
        return []
    plan = []
    for image in sorted(images, key=lambda item: int(item["index"])):
        source = str(image["path"])
        target_kb = parse_target_kb(image.get("target_kb")) or default_target_kb
        target_width = parse_target_kb(image.get("target_width"))
        target_height = parse_target_kb(image.get("target_height"))
        output = image.get("compressed_path") or compressed_path_for(source, target_kb, target_width, target_height)
        item = {"source": source, "output": str(output), "target_kb": target_kb}
        if target_width and target_height:
            item["target_width"] = target_width
            item["target_height"] = target_height
        plan.append(item)
    return plan


def apply_compression_plan(plan: List[Dict[str, Any]]) -> None:
    for item in plan:
        command = [
                sys.executable,
                str(IMAGE_COMPRESS_SCRIPT),
                item["source"],
                item["output"],
                "--target-kb",
                str(item["target_kb"]),
            ]
        if item.get("target_width") and item.get("target_height"):
            command.extend(["--target-width", str(item["target_width"]), "--target-height", str(item["target_height"])])
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "image compression failed").strip())


def run_best_effort_cleanup() -> Dict[str, Any]:
    if os.environ.get("ONION_AD_DISABLE_CLEANUP") == "1":
        return {"ok": True, "skipped": True, "reason": "ONION_AD_DISABLE_CLEANUP=1"}
    root = str(output_root())
    retention = os.environ.get("ONION_AD_ORIGINAL_RETENTION_DAYS", "7")
    result = subprocess.run(
        [
            sys.executable,
            str(IMAGE_CLEANUP_SCRIPT),
            "--root",
            root,
            "--original-retention-days",
            retention,
        ],
        text=True,
        capture_output=True,
    )
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"stdout": result.stdout.strip()}
    payload["exit_code"] = result.returncode
    if result.returncode != 0:
        payload["ok"] = False
        payload["stderr"] = result.stderr.strip()
    return payload


def infer_write_result_path(images: List[Dict[str, Any]]) -> Optional[Path]:
    paths = [Path(str(image["path"])).expanduser() for image in images if image.get("path")]
    if not paths:
        return None
    try:
        common = Path(os.path.commonpath([str(path.resolve()) for path in paths]))
    except ValueError:
        return None
    output_dir = common if common.is_dir() else common.parent
    if output_dir == output_dir.parent:
        return None
    return output_dir / "image-write-result.json"


def write_completion_marker(path: Optional[Path], payload: Dict[str, Any]) -> None:
    if not path:
        return
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def read_completion_marker(path: Optional[Path]) -> Dict[str, Any]:
    if not path:
        return {}
    path = path.expanduser().resolve()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def resumable_record_id(marker: Dict[str, Any]) -> Optional[str]:
    if marker.get("ok"):
        return None
    if marker.get("stage") not in {"record_created", "attachment_upload_failed"}:
        return None
    record_id = marker.get("record_id")
    return str(record_id) if record_id else None


def build_record_fields(
    direction_id: Optional[str],
    copy_id: Optional[str],
    parent_group_id: Optional[str],
    metadata: Dict[str, Any],
    images: List[Dict[str, Any]],
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    if direction_id:
        fields["关联方向"] = [direction_id]
    if copy_id:
        fields["关联文案"] = [copy_id]
    if parent_group_id:
        fields["父图组"] = [parent_group_id]
    for key, value in metadata.items():
        if key not in fields:
            fields[key] = value
    fields.setdefault("状态", "待用")
    for image in sorted(images, key=lambda item: int(item["index"])):
        prompt = image.get("prompt")
        if prompt:
            fields[f"图{int(image['index'])}提示词"] = prompt
    return fields


def build_attachments(images: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    attachments = []
    for image in sorted(images, key=lambda item: int(item["index"])):
        path = str(image["path"])
        attachments.append(
            {
                "field_id": f"图{int(image['index'])}",
                "file": path,
                "name": image.get("name") or Path(path).name,
            }
        )
    return attachments


def build_attachments_from_images(images: List[Dict[str, Any]], compression_plan: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    by_source = {item["source"]: item for item in compression_plan}
    attachments = []
    for image in sorted(images, key=lambda item: int(item["index"])):
        source = str(image["path"])
        planned = by_source.get(source)
        path = planned["output"] if planned else source
        attachments.append(
            {
                "field_id": f"图{int(image['index'])}",
                "file": path,
                "name": image.get("name") or Path(path).name,
            }
        )
    return attachments


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an image_groups record and upload generated PNG attachments.")
    parser.add_argument("--base-token")
    parser.add_argument("--table-id", default=DEFAULT_IMAGE_GROUPS_TABLE_ID)
    parser.add_argument("--direction-id")
    parser.add_argument("--copy-id")
    parser.add_argument("--parent-group-id")
    parser.add_argument("--images", required=True, help='JSON array of paths or objects: ["/tmp/a.png"] or [{"index": 1, "path": "...", "prompt": "..."}]')
    parser.add_argument("--metadata", required=True, help="JSON object with image group metadata fields")
    parser.add_argument("--package-zip", help="Local accepted-images zip path created before Base write")
    parser.add_argument("--target-kb", type=int, help="Default compressed image target size in KB; metadata 目标KB and per-image target_kb can also set it")
    parser.add_argument("--no-compress", action="store_true", help="Upload original image files instead of compressed JPGs")
    parser.add_argument("--write-result", help="Path to write a completion marker JSON after successful record and attachment upload")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        base_ops.load_env()
        images = normalize_images(json.loads(args.images))
        raw_metadata = json.loads(args.metadata)
        if not isinstance(raw_metadata, dict):
            raise ValueError("--metadata must be a JSON object")
        default_target_kb = resolve_default_target_kb(args.target_kb, raw_metadata)
        metadata = strip_control_metadata(raw_metadata)
        parent_group_id = normalize_parent(args.parent_group_id)
        record_fields = build_record_fields(args.direction_id, args.copy_id, parent_group_id, metadata, images)
        record_payload = build_lark_payload([{"fields": record_fields}])
        compression_plan = build_compression_plan(images, default_target_kb, not args.no_compress)
        attachments = build_attachments_from_images(images, compression_plan)
        package_zip = str(Path(args.package_zip).expanduser().resolve()) if args.package_zip else None
        marker_path = Path(args.write_result) if args.write_result else infer_write_result_path(images)
        existing_marker = read_completion_marker(marker_path)
        base_payload = {
            "base_token": base_ops.base_token(args.base_token),
            "table_id": args.table_id,
            "as_identity": "user",
            "lark_payload": record_payload,
        }

        if args.dry_run:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "operation": "image_group_create",
                        "dry_run": True,
                        "table_id": args.table_id,
                        "record_payload": record_payload,
                        "attachments": attachments,
                        "compression": compression_plan,
                        "package_zip": package_zip,
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        if existing_marker.get("ok") and existing_marker.get("record_id"):
            existing_marker.setdefault("skipped", True)
            existing_marker.setdefault("reason", "write_result_already_complete")
            print(json.dumps(existing_marker, ensure_ascii=False))
            return 0

        apply_compression_plan(compression_plan)
        record_id = resumable_record_id(existing_marker)
        resumed = bool(record_id)
        if not record_id:
            code, response = base_ops.execute_with_retry_or_pending("record_batch_create", base_payload)
            if code != 0:
                print(json.dumps(response, ensure_ascii=False))
                return code
            record_ids = response.get("record_ids") or []
            if not record_ids:
                print(json.dumps({"ok": False, "error": "record create succeeded but returned no record id"}, ensure_ascii=False), file=sys.stderr)
                return 6
            record_id = record_ids[0]
            write_completion_marker(
                marker_path,
                {
                    "ok": False,
                    "stage": "record_created",
                    "record_id": record_id,
                    "direction_id": args.direction_id,
                    "copy_id": args.copy_id,
                    "parent_group_id": parent_group_id,
                    "package_zip": package_zip,
                    "attachments": [],
                    "resume_command": "rerun write_image_group.py with the same --write-result to resume attachment upload",
                },
            )

        attachment_results = []
        for attachment in attachments:
            payload = {
                "base_token": base_payload["base_token"],
                "table_id": args.table_id,
                "as_identity": "user",
                "record_id": record_id,
                **attachment,
            }
            attach_code, attach_response = base_ops.execute_with_retry_or_pending("attachment_upload", payload)
            attachment_results.append({"field_id": attachment["field_id"], "result": attach_response, "exit_code": attach_code})
            if attach_code != 0:
                failure = {
                    "ok": False,
                    "stage": "attachment_upload_failed",
                    "record_id": record_id,
                    "direction_id": args.direction_id,
                    "copy_id": args.copy_id,
                    "parent_group_id": parent_group_id,
                    "package_zip": package_zip,
                    "attachments": attachment_results,
                    "resume_command": "rerun write_image_group.py with the same --write-result to resume attachment upload",
                }
                write_completion_marker(marker_path, failure)
                print(json.dumps(failure, ensure_ascii=False))
                return attach_code
        cleanup_result = run_best_effort_cleanup()
        output = {
            "ok": True,
            "stage": "complete",
            "record_id": record_id,
            "direction_id": args.direction_id,
            "copy_id": args.copy_id,
            "parent_group_id": parent_group_id,
            "package_zip": package_zip,
            "attachments": attachment_results,
            "cleanup": cleanup_result,
            "resumed": resumed,
        }
        write_completion_marker(marker_path, output)
        if marker_path:
            output["write_result_path"] = str(marker_path.expanduser().resolve())
        print(json.dumps(output, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
