from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional

import base_ops


TABLES: Dict[str, Dict[str, Any]] = {
    "directions": {
        "table_id": "tblLWPSHrZT95oy7",
        "env": "ONION_BASE_DIRECTIONS_TID",
        "id_field": "方向ID",
        "prefix": "D",
        "default_fields": [
            "方向ID",
            "素材方向",
            "功能",
            "卖点",
            "目标人群",
            "适配阶段",
            '1 能解决用户在"具体哪个场景里的哪个问题"',
            '2 能带来什么不一样的"一听很惊艳"的解法？',
            '3 因此带来了哪个场景下的什么"奇效"？',
            "状态",
        ],
    },
    "copies": {
        "table_id": "tblFdwXSbjANQjlh",
        "env": "ONION_BASE_COPIES_TID",
        "id_field": "文案ID",
        "prefix": "C",
        "default_fields": [
            "文案ID",
            "关联方向",
            "渠道",
            "图片形式",
            "文案类型",
            "主标题",
            "副标题",
            "短句1",
            "短句2",
            "短句3",
            "状态",
        ],
    },
    "image_groups": {
        "table_id": "tblGpuukciptN3PP",
        "env": "ONION_BASE_IMAGE_GROUPS_TID",
        "id_field": "图组ID",
        "prefix": "G",
        "default_fields": [
            "图组ID",
            "关联方向",
            "关联文案",
            "渠道",
            "图片形式",
            "版位",
            "比例",
            "IP形象",
            "IP参考图引用",
            "Logo",
            "Logo参考图引用",
            "CTA文字",
            "风格参考图引用",
            "图1提示词",
            "图2提示词",
            "图3提示词",
            "状态",
            "父图组",
        ],
        "attachment_fields": ["图1", "图2", "图3", "风格参考图_用户上传"],
    },
    "feedbacks": {
        "table_id": "tblsPpNNcNH5KXoZ",
        "env": "ONION_BASE_FEEDBACKS_TID",
        "id_field": "反馈ID",
        "prefix": "F",
        "default_fields": [
            "反馈ID",
            "反馈对象类型",
            "被反馈对象ID",
            "反馈类型",
            "反馈内容",
            "建议改法",
            "处置状态",
        ],
    },
}


ID_RE = re.compile(r"^(?P<prefix>[DCGF])-\d+$", re.IGNORECASE)


def table_id(config: Dict[str, Any]) -> str:
    base_ops.load_env()
    return os.environ.get(config["env"]) or config["table_id"]


def infer_table_key(identifier: str) -> Optional[str]:
    match = ID_RE.match(identifier.strip())
    if not match:
        return None
    prefix = match.group("prefix").upper()
    for key, config in TABLES.items():
        if config["prefix"] == prefix:
            return key
    return None


def resolve_table_key(identifier: str, table: Optional[str]) -> str:
    if table:
        if table in TABLES:
            return table
        raise ValueError(f"unknown table alias: {table}")
    inferred = infer_table_key(identifier)
    if inferred:
        return inferred
    if identifier.startswith("rec"):
        raise ValueError("record_id starts with rec; pass --table directions|copies|image_groups|feedbacks")
    raise ValueError("cannot infer table from id; use D-XXX, C-XXX, G-XXX, F-XXX or pass --table with record_id")


def default_fields(config: Dict[str, Any], include_attachments: bool) -> List[str]:
    fields = list(config["default_fields"])
    if include_attachments:
        fields.extend(config.get("attachment_fields") or [])
    return fields


def build_record_get_command(
    *,
    base_token: str,
    table_id_value: str,
    record_ids: List[str],
    fields: List[str],
) -> List[str]:
    command = [
        base_ops.lark_bin(),
        "base",
        "+record-get",
        "--base-token",
        base_token,
        "--table-id",
        table_id_value,
        "--format",
        "json",
        "--as",
        "user",
    ]
    for record_id in record_ids:
        command.extend(["--record-id", record_id])
    for field in fields:
        command.extend(["--field-id", field])
    return command


def build_record_search_command(
    *,
    base_token: str,
    table_id_value: str,
    id_field: str,
    identifier: str,
) -> List[str]:
    search_json = {
        "keyword": identifier,
        "search_fields": [id_field],
        "select_fields": [id_field],
        "limit": 5,
    }
    return [
        base_ops.lark_bin(),
        "base",
        "+record-search",
        "--base-token",
        base_token,
        "--table-id",
        table_id_value,
        "--json",
        json.dumps(search_json, ensure_ascii=False),
        "--format",
        "json",
        "--as",
        "user",
    ]


def build_record_list_command(
    *,
    base_token: str,
    table_id_value: str,
    id_field: str,
) -> List[str]:
    return [
        base_ops.lark_bin(),
        "base",
        "+record-list",
        "--base-token",
        base_token,
        "--table-id",
        table_id_value,
        "--field-id",
        id_field,
        "--limit",
        "200",
        "--format",
        "json",
        "--as",
        "user",
    ]


def run_json(command: List[str]) -> Dict[str, Any]:
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"exit code {result.returncode}").strip())
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"lark-cli returned non-JSON output: {result.stdout[:500]}") from exc


def normalize_records(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    current = raw.get("data", raw)
    if not isinstance(current, dict):
        return []

    records = current.get("records")
    if isinstance(records, list):
        normalized = []
        for record in records:
            if not isinstance(record, dict):
                continue
            record_id = record.get("record_id") or record.get("id")
            fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
            if record_id:
                normalized.append({"record_id": str(record_id), "fields": fields})
        return normalized

    record_ids = current.get("record_id_list") or current.get("record_ids")
    field_names = current.get("fields") or current.get("field_id_list")
    rows = current.get("data") or current.get("rows")
    if isinstance(record_ids, list) and isinstance(field_names, list) and isinstance(rows, list):
        normalized = []
        for index, record_id in enumerate(record_ids):
            row = rows[index] if index < len(rows) else []
            fields = {}
            if isinstance(row, list):
                fields = {
                    str(field_names[pos]): row[pos]
                    for pos in range(min(len(field_names), len(row)))
                }
            normalized.append({"record_id": str(record_id), "fields": fields})
        return normalized

    return []


def field_value(fields: Dict[str, Any], name: str) -> Any:
    return fields.get(name)


def find_record_id_by_business_id(
    *,
    base_token: str,
    config: Dict[str, Any],
    table_id_value: str,
    identifier: str,
) -> str:
    id_field = config["id_field"]
    search = run_json(
        build_record_search_command(
            base_token=base_token,
            table_id_value=table_id_value,
            id_field=id_field,
            identifier=identifier,
        )
    )
    for record in normalize_records(search):
        if str(field_value(record["fields"], id_field) or "").strip() == identifier:
            return record["record_id"]
    candidates = normalize_records(search)
    if len(candidates) == 1:
        return candidates[0]["record_id"]

    listing = run_json(
        build_record_list_command(
            base_token=base_token,
            table_id_value=table_id_value,
            id_field=id_field,
        )
    )
    matches = [
        record
        for record in normalize_records(listing)
        if str(field_value(record["fields"], id_field) or "").strip() == identifier
    ]
    if len(matches) == 1:
        return matches[0]["record_id"]
    if len(matches) > 1:
        raise RuntimeError(f"multiple records matched {identifier}")
    raise RuntimeError(f"record not found: {identifier}")


def get_records(
    *,
    base_token: str,
    table_key: str,
    record_ids: List[str],
    fields: List[str],
) -> List[Dict[str, Any]]:
    config = TABLES[table_key]
    raw = run_json(
        build_record_get_command(
            base_token=base_token,
            table_id_value=table_id(config),
            record_ids=record_ids,
            fields=fields,
        )
    )
    return normalize_records(raw)


def extract_link_record_ids(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.startswith("rec") else []
    if isinstance(value, dict):
        for key in ("record_id", "id"):
            item = value.get(key)
            if isinstance(item, str) and item.startswith("rec"):
                return [item]
        return []
    if isinstance(value, list):
        ids: List[str] = []
        for item in value:
            ids.extend(extract_link_record_ids(item))
        return ids
    return []


def append_unique_record_ids(target: List[str], candidates: List[str]) -> None:
    seen = set(target)
    for candidate in candidates:
        if candidate not in seen:
            target.append(candidate)
            seen.add(candidate)


def linked_records(base_token: str, table_key: str, record: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    fields = record.get("fields") or {}
    linked: Dict[str, List[Dict[str, Any]]] = {}
    direction_ids: List[str] = []
    if table_key in {"copies", "image_groups"}:
        append_unique_record_ids(direction_ids, extract_link_record_ids(fields.get("关联方向")))
    if table_key == "image_groups":
        copy_ids = extract_link_record_ids(fields.get("关联文案"))
        if copy_ids:
            copy_records = get_records(
                base_token=base_token,
                table_key="copies",
                record_ids=copy_ids,
                fields=default_fields(TABLES["copies"], include_attachments=False),
            )
            linked["copies"] = copy_records
            for copy_record in copy_records:
                append_unique_record_ids(
                    direction_ids,
                    extract_link_record_ids((copy_record.get("fields") or {}).get("关联方向")),
                )
    if direction_ids:
        linked["directions"] = get_records(
            base_token=base_token,
            table_key="directions",
            record_ids=direction_ids,
            fields=default_fields(TABLES["directions"], include_attachments=False),
        )
    return linked


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve D/C/G/F IDs or record_id to normalized Base record JSON.")
    parser.add_argument("--base-token")
    parser.add_argument("--table", choices=sorted(TABLES.keys()))
    parser.add_argument("--id", required=True, help="D-XXX, C-XXX, G-XXX, F-XXX, or rec... when --table is set")
    parser.add_argument("--field", action="append", help="Project extra fields. Defaults are task-safe fields.")
    parser.add_argument("--include-attachments", action="store_true")
    parser.add_argument("--follow-upstream", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        identifier = args.id.strip()
        table_key = resolve_table_key(identifier, args.table)
        config = TABLES[table_key]
        base_token = base_ops.base_token(args.base_token)
        fields = args.field or default_fields(config, args.include_attachments)
        table_id_value = table_id(config)

        if identifier.startswith("rec"):
            record_id = identifier
            lookup_command = None
        else:
            lookup_command = build_record_search_command(
                base_token=base_token,
                table_id_value=table_id_value,
                id_field=config["id_field"],
                identifier=identifier,
            )
            record_id = None

        get_command = build_record_get_command(
            base_token=base_token,
            table_id_value=table_id_value,
            record_ids=[record_id or "<resolved-record-id>"],
            fields=fields,
        )

        if args.dry_run:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "dry_run": True,
                        "table": table_key,
                        "input_id": identifier,
                        "lookup_command": lookup_command,
                        "get_command": get_command,
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        if record_id is None:
            record_id = find_record_id_by_business_id(
                base_token=base_token,
                config=config,
                table_id_value=table_id_value,
                identifier=identifier,
            )
        records = get_records(base_token=base_token, table_key=table_key, record_ids=[record_id], fields=fields)
        if not records:
            raise RuntimeError(f"record-get returned no records for {record_id}")
        record = records[0]
        payload: Dict[str, Any] = {
            "ok": True,
            "table": table_key,
            "input_id": identifier,
            "record_id": record["record_id"],
            "fields": record["fields"],
        }
        if args.follow_upstream:
            payload["linked"] = linked_records(base_token, table_key, record)
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
