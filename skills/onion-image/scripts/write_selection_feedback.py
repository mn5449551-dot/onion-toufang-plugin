#!/usr/bin/env python3
"""
Write rejected image-selection feedback into the shared feedbacks table.

The selection page stores accepted schemes and rejected scheme annotations in
image-selection-result.json. Accepted schemes are for image_groups. Rejected
scheme annotations with concrete user text become feedbacks records.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parents[2]
WRITE_RECORD_SCRIPT = PLUGIN_ROOT / "shared" / "scripts" / "write_record.py"
DEFAULT_FEEDBACK_TABLE_ID = "tblsPpNNcNH5KXoZ"
SKIP_REASONS = {"跳过", "跳过反馈", "说不清楚", "无具体反馈"}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("selection result must be a JSON object")
    return data


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def annotation_for(scheme: dict[str, Any]) -> dict[str, Any]:
    annotation = scheme.get("annotation")
    if isinstance(annotation, dict):
        return annotation
    return {
        "reason": scheme.get("reason"),
        "ruleFeedback": scheme.get("ruleFeedback") or scheme.get("rule_feedback"),
        "note": scheme.get("note"),
        "problemPositions": scheme.get("problemPositions") or scheme.get("problem_positions"),
    }


def annotation_positions(annotation: dict[str, Any]) -> list[str]:
    value = annotation.get("problem_positions")
    if value is None:
        value = annotation.get("problemPositions")
    if value is None:
        value = []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [clean_text(item) for item in value if clean_text(item)]


def skip_feedback(annotation: dict[str, Any]) -> bool:
    if bool(annotation.get("skip_feedback") or annotation.get("skipFeedback")):
        return True
    reason = clean_text(annotation.get("reason"))
    return reason in SKIP_REASONS


def fixed_rule_feedback(annotation: dict[str, Any]) -> str:
    return clean_text(
        annotation.get("fixed_rule_feedback")
        or annotation.get("fixedRuleFeedback")
        or annotation.get("ruleFeedback")
        or annotation.get("rule_feedback")
    )


def subjective_feedback(annotation: dict[str, Any]) -> str:
    return clean_text(
        annotation.get("subjective_feedback")
        or annotation.get("subjectiveFeedback")
        or annotation.get("note")
    )


def scheme_id_for(scheme: dict[str, Any], position: int) -> str:
    return clean_text(scheme.get("set_id") or scheme.get("id") or f"set{position}")


def meta_value(scheme: dict[str, Any], normalized: str, aliases: tuple[str, ...]) -> str:
    meta = scheme.get("meta") if isinstance(scheme.get("meta"), dict) else {}
    for source in (meta, scheme):
        for key in aliases:
            value = clean_text(source.get(key))
            if value:
                return value
    return ""


def rejected_schemes(selection: dict[str, Any]) -> list[dict[str, Any]]:
    rejected = selection.get("rejected_schemes")
    if isinstance(rejected, list):
        return [item for item in rejected if isinstance(item, dict)]

    # Fallback for copied compact JSON that only includes `schemes`.
    schemes = selection.get("schemes")
    if not isinstance(schemes, list):
        return []
    return [
        item
        for item in schemes
        if isinstance(item, dict) and item.get("decision") == "rejected"
    ]


def feedback_object_id(request_id: str, scheme: dict[str, Any], position: int) -> str:
    for key in ("image_group_id", "imageGroupId", "图组ID", "group_id", "G-ID"):
        value = clean_text(scheme.get(key))
        if value:
            return value
    source = scheme.get("source") if isinstance(scheme.get("source"), dict) else {}
    for key in ("imageGroupId", "image_group_id", "图组ID", "groupId"):
        value = clean_text(source.get(key))
        if value:
            return value
    set_id = clean_text(scheme.get("set_id") or scheme.get("id") or f"set{position}")
    return f"{request_id}/{set_id}"


def copy_record_id_for(scheme: dict[str, Any]) -> str:
    for key in ("copy_record_id", "copyRecordId", "文案记录ID", "文案record_id"):
        value = clean_text(scheme.get(key))
        if value:
            return value
    source = scheme.get("source") if isinstance(scheme.get("source"), dict) else {}
    for key in ("copyRecordId", "copy_record_id", "文案记录ID", "文案record_id"):
        value = clean_text(source.get(key))
        if value:
            return value
    meta = scheme.get("meta") if isinstance(scheme.get("meta"), dict) else {}
    for key in ("copyRecordId", "copy_record_id", "文案记录ID", "文案record_id"):
        value = clean_text(meta.get(key))
        if value:
            return value
    return ""


def context_note(scheme: dict[str, Any], annotation: dict[str, Any], request_id: str, object_id: str) -> str:
    parts = [f"来源：{object_id}"]
    for label, keys in (
        ("渠道", ("渠道", "channel")),
        ("版位", ("版位", "placement")),
        ("图片形式", ("图片形式", "form")),
    ):
        value = meta_value(scheme, label, keys)
        if value:
            parts.append(f"{label}：{value}")
    positions = annotation_positions(annotation)
    if positions:
        parts.append("问题图位：" + "、".join(positions))
    if request_id and request_id not in object_id:
        parts.append(f"请求：{request_id}")
    return "；".join(parts)


def make_feedback_record(
    object_id: str,
    feedback_type: str,
    content: str,
    suggestion: str,
    *,
    request_id: str,
    scheme_id: str,
    scheme: dict[str, Any],
    annotation: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "反馈对象类型": "图组",
        "被反馈对象ID": object_id,
        "反馈类型": feedback_type,
        "反馈内容": content,
        "建议改法": suggestion,
        "处置状态": "待审",
    }
    if request_id:
        fields["请求ID"] = request_id
    if scheme_id:
        fields["方案ID"] = scheme_id
    copy_record_id = copy_record_id_for(scheme)
    if copy_record_id:
        fields["关联文案"] = [copy_record_id]
    positions = annotation_positions(annotation)
    if positions:
        fields["问题图位"] = "、".join(positions)
    for field, aliases in (
        ("渠道", ("渠道", "channel")),
        ("版位", ("版位", "placement")),
        ("图片形式", ("图片形式", "form", "image_form", "imageForm")),
    ):
        value = meta_value(scheme, field, aliases)
        if value:
            fields[field] = value
    return {"fields": fields}


def feedback_records_from_selection(selection: dict[str, Any]) -> list[dict[str, Any]]:
    request_id = clean_text(selection.get("request_id") or selection.get("requestId") or "")
    records: list[dict[str, Any]] = []
    for position, scheme in enumerate(rejected_schemes(selection), start=1):
        annotation = annotation_for(scheme)
        if skip_feedback(annotation):
            continue
        object_id = feedback_object_id(request_id or "unknown-request", scheme, position)
        scheme_id = scheme_id_for(scheme, position)
        note = context_note(scheme, annotation, request_id, object_id)
        rule_feedback = fixed_rule_feedback(annotation)
        user_subjective_feedback = subjective_feedback(annotation)
        if rule_feedback:
            records.append(
                make_feedback_record(
                    object_id,
                    "固定规则反馈",
                    rule_feedback,
                    note,
                    request_id=request_id,
                    scheme_id=scheme_id,
                    scheme=scheme,
                    annotation=annotation,
                )
            )
        if user_subjective_feedback:
            records.append(
                make_feedback_record(
                    object_id,
                    "主观感受反馈",
                    user_subjective_feedback,
                    note,
                    request_id=request_id,
                    scheme_id=scheme_id,
                    scheme=scheme,
                    annotation=annotation,
                )
            )
    return records


def selection_feedback_errors(selection: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for position, scheme in enumerate(rejected_schemes(selection), start=1):
        annotation = annotation_for(scheme)
        set_id = scheme_id_for(scheme, position)
        if skip_feedback(annotation):
            continue
        if not fixed_rule_feedback(annotation) and not subjective_feedback(annotation):
            errors.append(f"{set_id}: 不采纳必须填写固定规则反馈 / 主观感受反馈 / 跳过反馈")
    return errors


def write_records(records: list[dict[str, Any]], table_id: str, base_token: str | None, dry_run: bool) -> tuple[int, dict[str, Any]]:
    command = [
        sys.executable,
        str(WRITE_RECORD_SCRIPT),
        "--table-id",
        table_id,
        "--records",
        json.dumps(records, ensure_ascii=False),
    ]
    if base_token:
        command.extend(["--base-token", base_token])
    if dry_run:
        command.append("--dry-run")

    result = subprocess.run(command, text=True, capture_output=True)
    output = result.stdout.strip() or result.stderr.strip() or "{}"
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        payload = {"ok": False, "raw_output": output}
    return result.returncode, payload


def persist_result(path: Path | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def default_write_result(selection_result: Path) -> Path:
    return selection_result.expanduser().resolve().parent / "image-feedback-result.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write rejected image selection feedback to feedbacks Base table.")
    parser.add_argument("--selection-result", required=True, help="Path to image-selection-result.json")
    parser.add_argument("--write-result", help="Output JSON marker; defaults beside selection result")
    parser.add_argument("--table-id", default=DEFAULT_FEEDBACK_TABLE_ID)
    parser.add_argument("--base-token")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        selection_path = Path(args.selection_result).expanduser().resolve()
        selection = load_json(selection_path)
        feedback_errors = selection_feedback_errors(selection)
        if feedback_errors:
            result_path = Path(args.write_result).expanduser().resolve() if args.write_result else default_write_result(selection_path)
            payload = {
                "ok": False,
                "error": "invalid_rejected_feedback",
                "errors": feedback_errors,
                "selection_result": str(selection_path),
                "write_result": str(result_path),
            }
            persist_result(result_path, payload)
            print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
            return 2
        records = feedback_records_from_selection(selection)
        result_path = Path(args.write_result).expanduser().resolve() if args.write_result else default_write_result(selection_path)
        if not records:
            payload = {
                "ok": True,
                "feedback_count": 0,
                "records": [],
                "selection_result": str(selection_path),
                "write_result": str(result_path),
                "skipped": True,
            }
            persist_result(result_path, payload)
            print(json.dumps(payload, ensure_ascii=False))
            return 0

        code, write_payload = write_records(records, args.table_id, args.base_token, args.dry_run)
        ok = code in {0, 5}
        payload = {
            "ok": ok,
            "dry_run": args.dry_run,
            "feedback_count": len(records),
            "records": records,
            "selection_result": str(selection_path),
            "write_result": str(result_path),
            "table_id": args.table_id,
            "write_record_result": write_payload,
        }
        persist_result(result_path, payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if ok else code
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
