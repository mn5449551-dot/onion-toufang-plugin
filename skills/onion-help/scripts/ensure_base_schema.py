#!/usr/bin/env python3
"""Ensure the shared Onion Feishu Base has the fields required by this plugin.

Default mode is dry-run: print missing fields, unsafe differences, and commands.
Use --apply only after the maintainer has confirmed the target Base is correct.
View ordering is skipped unless explicit view ids are passed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parents[2]
SHARED_SCRIPTS = PLUGIN_ROOT / "shared" / "scripts"
if str(SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS))
import base_ops  # noqa: E402


DEFAULT_TABLES = {
    "directions": "tblLWPSHrZT95oy7",
    "image_groups": "tblGpuukciptN3PP",
    "copies": "tblFdwXSbjANQjlh",
    "feedbacks": "tblsPpNNcNH5KXoZ",
}
REDACTED = "***REDACTED***"
SENSITIVE_KEYS = {"base_token", "app_token", "token"}


IMAGE_GROUP_FIELDS = [
    {"name": "请求ID", "type": "text", "description": "本地批量请求 request_id，用于对齐选择页、zip、manifest。"},
    {"name": "方案ID", "type": "text", "description": "本地图片方案 set_id，用于回查选择页标注结果。"},
]


DIRECTION_FUNCTION_FIELD = {
    "name": "功能",
    "type": "select",
    "multiple": False,
    "options": [
        {"name": "拍题精学", "hue": "Blue", "lightness": "Lighter"},
        {"name": "同步课", "hue": "Green", "lightness": "Lighter"},
        {"name": "总复习", "hue": "Purple", "lightness": "Lighter"},
        {"name": "学情报告", "hue": "Orange", "lightness": "Lighter"},
        {"name": "AI私教动画课", "hue": "Wathet", "lightness": "Lighter"},
        {"name": "AI定制班", "hue": "Carmine", "lightness": "Lighter"},
        {"name": "洋葱私教班", "hue": "Yellow", "lightness": "Lighter"},
        {"name": "错题本", "hue": "Red", "lightness": "Lighter"},
        {"name": "其他", "hue": "Gray", "lightness": "Lighter"},
    ],
}


def feedback_fields(copies_tid: str) -> list[dict[str, Any]]:
    return [
        {
            "name": "关联文案",
            "type": "link",
            "link_table": copies_tid,
            "bidirectional": False,
            "description": "图片选择页反馈对应的 copies 记录；未采纳图没有 G-ID 时也用它追溯 C-XXX。",
        },
        {"name": "请求ID", "type": "text", "description": "图片标注页 request_id。"},
        {"name": "方案ID", "type": "text", "description": "本地图片方案 set_id。"},
        {"name": "问题图位", "type": "text", "description": "多个图位用顿号连接，如 图1、图2。"},
        {"name": "渠道", "type": "text", "description": "反馈发生时的渠道快照。"},
        {"name": "版位", "type": "text", "description": "反馈发生时的版位快照。"},
        {"name": "图片形式", "type": "text", "description": "单图 / 双图 / 三图。"},
    ]


FEEDBACK_TYPE_FIELD = {
    "name": "反馈类型",
    "type": "select",
    "multiple": False,
    "options": [
        {"name": "固定规则反馈", "hue": "Red", "lightness": "Lighter"},
        {"name": "主观感受反馈", "hue": "Orange", "lightness": "Lighter"},
    ],
}


VIEW_ORDERS = {
    "image_groups": [
        "图组ID",
        "状态",
        "图1",
        "图1提示词",
        "图2",
        "图2提示词",
        "图3",
        "图3提示词",
        "渠道",
        "图片形式",
        "版位",
        "关联文案",
        "关联方向",
        "IP形象",
        "Logo",
        "CTA文字",
        "父图组",
        "请求ID",
        "方案ID",
        "比例",
        "IP参考图引用",
        "Logo参考图引用",
        "风格参考图引用",
        "风格参考图_用户上传",
        "创建人",
        "创建时间",
        "最后更新时间",
    ],
    "feedbacks": [
        "反馈ID",
        "处置状态",
        "反馈类型",
        "反馈内容",
        "关联文案",
        "反馈对象类型",
        "被反馈对象ID",
        "问题图位",
        "渠道",
        "版位",
        "图片形式",
        "请求ID",
        "方案ID",
        "建议改法",
        "处置备注",
        "创建人",
        "创建时间",
        "最后更新时间",
    ],
}


def env_table_ids() -> dict[str, str]:
    base_ops.load_env()
    return {
        "directions": os.environ.get("ONION_BASE_DIRECTIONS_TID") or DEFAULT_TABLES["directions"],
        "image_groups": os.environ.get("ONION_BASE_IMAGE_GROUPS_TID") or DEFAULT_TABLES["image_groups"],
        "copies": os.environ.get("ONION_BASE_COPIES_TID") or DEFAULT_TABLES["copies"],
        "feedbacks": os.environ.get("ONION_BASE_FEEDBACKS_TID") or DEFAULT_TABLES["feedbacks"],
    }


def extract_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    if start < 0:
        raise ValueError(f"lark-cli returned no JSON: {stdout[:200]}")
    return json.loads(stdout[start:])


def run_lark(args: list[str], *, apply: bool) -> dict[str, Any]:
    if not apply:
        return {"ok": True, "dry_run": True, "command": redact_command(args)}
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = result.stdout or result.stderr
    payload = extract_json(output) if "{" in output else {"ok": result.returncode == 0, "raw": output.strip()}
    payload["exit_code"] = result.returncode
    payload["command"] = redact_command(args)
    if result.returncode != 0:
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


def redact_command(command: list[Any]) -> list[Any]:
    redacted = []
    hide_next = False
    for item in command:
        if hide_next:
            redacted.append(REDACTED)
            hide_next = False
            continue
        redacted.append(item)
        if str(item) in {"--base-token", "--app-token", "--token"}:
            hide_next = True
    return redacted


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in SENSITIVE_KEYS or key_text.endswith("_token"):
                result[key] = REDACTED
            elif key == "command" and isinstance(item, list):
                result[key] = redact_command(item)
            else:
                result[key] = redact_sensitive(item)
        return result
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def field_list(base_token: str, table_id: str) -> list[dict[str, Any]]:
    command = [
        base_ops.lark_bin(),
        "base",
        "+field-list",
        "--as",
        "user",
        "--base-token",
        base_token,
        "--table-id",
        table_id,
        "--limit",
        "100",
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    payload = extract_json(result.stdout or result.stderr)
    return list(payload.get("data", {}).get("fields") or [])


def view_list(base_token: str, table_id: str) -> list[dict[str, Any]]:
    command = [
        base_ops.lark_bin(),
        "base",
        "+view-list",
        "--as",
        "user",
        "--base-token",
        base_token,
        "--table-id",
        table_id,
        "--limit",
        "100",
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    payload = extract_json(result.stdout or result.stderr)
    return list(payload.get("data", {}).get("views") or [])


def create_field(base_token: str, table_id: str, field: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    return run_lark(
        [
            base_ops.lark_bin(),
            "base",
            "+field-create",
            "--as",
            "user",
            "--base-token",
            base_token,
            "--table-id",
            table_id,
            "--json",
            json.dumps(field, ensure_ascii=False),
        ],
        apply=apply,
    )


def option_names(options: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("name")) for item in options if item.get("name")]


def clean_select_option(option: dict[str, Any]) -> dict[str, Any]:
    cleaned = {"name": str(option.get("name") or "")}
    for key in ("hue", "lightness"):
        if option.get(key):
            cleaned[key] = option[key]
    return {key: value for key, value in cleaned.items() if value}


def merge_select_options(existing_options: list[dict[str, Any]], desired_options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = [clean_select_option(item) for item in existing_options if item.get("name")]
    existing_names = set(option_names(merged))
    for option in desired_options:
        name = str(option.get("name") or "")
        if name and name not in existing_names:
            merged.append(clean_select_option(option))
            existing_names.add(name)
    return merged


def select_payload_with_options(template: dict[str, Any], options: list[dict[str, Any]]) -> dict[str, Any]:
    payload = dict(template)
    payload["options"] = options
    return payload


def update_feedback_type(base_token: str, feedbacks_tid: str, field: dict[str, Any], payload: dict[str, Any] | None = None, *, apply: bool) -> dict[str, Any]:
    field_payload = payload or FEEDBACK_TYPE_FIELD
    return run_lark(
        [
            base_ops.lark_bin(),
            "base",
            "+field-update",
            "--as",
            "user",
            "--base-token",
            base_token,
            "--table-id",
            feedbacks_tid,
            "--field-id",
            field["id"],
            "--json",
            json.dumps(field_payload, ensure_ascii=False),
            "--yes",
        ],
        apply=apply,
    )


def update_direction_function(base_token: str, directions_tid: str, field: dict[str, Any], payload: dict[str, Any] | None = None, *, apply: bool) -> dict[str, Any]:
    field_payload = payload or DIRECTION_FUNCTION_FIELD
    return run_lark(
        [
            base_ops.lark_bin(),
            "base",
            "+field-update",
            "--as",
            "user",
            "--base-token",
            base_token,
            "--table-id",
            directions_tid,
            "--field-id",
            field["id"],
            "--json",
            json.dumps(field_payload, ensure_ascii=False),
            "--yes",
        ],
        apply=apply,
    )


def set_view_order(base_token: str, table_id: str, view_id: str, visible_fields: list[str], *, apply: bool) -> dict[str, Any]:
    return run_lark(
        [
            base_ops.lark_bin(),
            "base",
            "+view-set-visible-fields",
            "--as",
            "user",
            "--base-token",
            base_token,
            "--table-id",
            table_id,
            "--view-id",
            view_id,
            "--json",
            json.dumps({"visible_fields": visible_fields}, ensure_ascii=False),
        ],
        apply=apply,
    )


def ensure_table_fields(base_token: str, table_id: str, desired_fields: list[dict[str, Any]], *, apply: bool) -> list[dict[str, Any]]:
    fields = field_list(base_token, table_id)
    existing = {field["name"]: field for field in fields}
    results = []
    for desired in desired_fields:
        if desired["name"] in existing:
            results.append({"action": "exists", "field": desired["name"]})
            continue
        results.append({"action": "create", "field": desired["name"], "result": create_field(base_token, table_id, desired, apply=apply)})
    return results


def ensure_feedback_type_options(base_token: str, feedbacks_tid: str, *, apply: bool) -> dict[str, Any]:
    fields = field_list(base_token, feedbacks_tid)
    field = next((item for item in fields if item.get("name") == "反馈类型"), None)
    if not field:
        return {"action": "missing_feedback_type", "ok": False}
    existing_option_items = list(field.get("options") or [])
    desired_option_items = list(FEEDBACK_TYPE_FIELD["options"])
    existing_options = option_names(existing_option_items)
    desired_options = option_names(desired_option_items)
    missing_options = [name for name in desired_options if name not in existing_options]
    if not missing_options:
        return {"action": "exists", "field": "反馈类型", "options": existing_options}
    merged_options = merge_select_options(existing_option_items, desired_option_items)
    payload = select_payload_with_options(FEEDBACK_TYPE_FIELD, merged_options)
    return {
        "action": "update",
        "field": "反馈类型",
        "from": existing_options,
        "to": option_names(merged_options),
        "missing_options": missing_options,
        "result": update_feedback_type(base_token, feedbacks_tid, field, payload, apply=apply),
    }


def ensure_direction_function_options(base_token: str, directions_tid: str, *, apply: bool) -> dict[str, Any]:
    fields = field_list(base_token, directions_tid)
    field = next((item for item in fields if item.get("name") == "功能"), None)
    if not field:
        return {"action": "missing_direction_function", "ok": False}
    existing_option_items = list(field.get("options") or [])
    desired_option_items = list(DIRECTION_FUNCTION_FIELD["options"])
    existing_options = option_names(existing_option_items)
    desired_options = option_names(desired_option_items)
    missing_options = [name for name in desired_options if name not in existing_options]
    if not missing_options:
        return {"action": "exists", "field": "功能", "options": existing_options}
    merged_options = merge_select_options(existing_option_items, desired_option_items)
    payload = select_payload_with_options(DIRECTION_FUNCTION_FIELD, merged_options)
    return {
        "action": "update",
        "field": "功能",
        "from": existing_options,
        "to": option_names(merged_options),
        "missing_options": missing_options,
        "result": update_direction_function(base_token, directions_tid, field, payload, apply=apply),
    }


def ensure_view_orders(base_token: str, tables: dict[str, str], *, apply: bool, view_ids: dict[str, str] | None = None) -> list[dict[str, Any]]:
    results = []
    view_ids = view_ids or {}
    for table_name, field_order in VIEW_ORDERS.items():
        view_id = str(view_ids.get(table_name) or "").strip()
        if not view_id:
            results.append(
                {
                    "table": table_name,
                    "action": "skipped_missing_view_id",
                    "next_action": f"Pass an explicit {table_name} view id to update visible fields.",
                }
            )
            continue
        fields = field_list(base_token, tables[table_name])
        by_name = {field.get("name"): field for field in fields}
        visible_field_ids = [by_name[name]["id"] for name in field_order if name in by_name and by_name[name].get("id")]
        missing = [name for name in field_order if name not in by_name]
        results.append(
            {
                "table": table_name,
                "view_id": view_id,
                "action": "set_visible_fields",
                "missing_fields": missing,
                "visible_fields": field_order,
                "visible_field_ids": visible_field_ids,
                "result": set_view_order(base_token, tables[table_name], view_id, visible_field_ids, apply=apply),
            }
        )
    return results


def ensure_schema(*, apply: bool, base_token: str | None = None, view_ids: dict[str, str] | None = None) -> dict[str, Any]:
    token = base_ops.base_token(base_token)
    tables = env_table_ids()
    return {
        "ok": True,
        "applied": apply,
        "base_token": REDACTED,
        "tables": tables,
        "direction_function": ensure_direction_function_options(token, tables["directions"], apply=apply),
        "image_groups": ensure_table_fields(token, tables["image_groups"], IMAGE_GROUP_FIELDS, apply=apply),
        "feedbacks": ensure_table_fields(token, tables["feedbacks"], feedback_fields(tables["copies"]), apply=apply),
        "feedback_type": ensure_feedback_type_options(token, tables["feedbacks"], apply=apply),
        "views": ensure_view_orders(token, tables, apply=apply, view_ids=view_ids),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ensure Onion shared Base schema and view order.")
    parser.add_argument("--base-token")
    parser.add_argument("--apply", action="store_true", help="Actually create/update fields and set view order. Default is dry-run.")
    parser.add_argument("--image-groups-view-id", help="Explicit image_groups view id to update visible fields.")
    parser.add_argument("--feedbacks-view-id", help="Explicit feedbacks view id to update visible fields.")
    args = parser.parse_args(argv)

    try:
        view_ids = {
            key: value
            for key, value in {
                "image_groups": args.image_groups_view_id,
                "feedbacks": args.feedbacks_view_id,
            }.items()
            if value
        }
        print(
            json.dumps(
                redact_sensitive(ensure_schema(apply=args.apply, base_token=args.base_token, view_ids=view_ids)),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
