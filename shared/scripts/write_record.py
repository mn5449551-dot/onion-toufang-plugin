from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from typing import Any, Dict, List

import base_ops


SYSTEM_MANAGED_FIELDS = {
    "创建时间",
    "创建人",
    "最后更新时间",
    "方向ID",
    "文案ID",
    "图组ID",
    "反馈ID",
}


def reject_system_managed_fields(field_names: List[str]) -> None:
    blocked = [field for field in field_names if field in SYSTEM_MANAGED_FIELDS]
    if blocked:
        raise ValueError(
            "system-managed fields must not be written: "
            + ", ".join(blocked)
            + ". Feishu Base fills IDs, creator and timestamps automatically from the lark-cli user identity."
        )


def build_lark_payload(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    fields = OrderedDict()
    for record in records:
        record_fields = record.get("fields")
        if not isinstance(record_fields, dict):
            raise ValueError("Each record must contain a fields object")
        for field in record_fields:
            fields.setdefault(field, None)
    field_names = list(fields.keys())
    reject_system_managed_fields(field_names)
    rows = []
    for record in records:
        record_fields = record["fields"]
        rows.append([record_fields.get(field) for field in field_names])
    return {"fields": field_names, "rows": rows}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create Base records through lark-cli fields/rows payloads.")
    parser.add_argument("--base-token")
    parser.add_argument("--table-id", required=True)
    parser.add_argument("--records", required=True, help='JSON array: [{"fields": {...}}]')
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        records = json.loads(args.records)
        if not isinstance(records, list) or not records:
            raise ValueError("--records must be a non-empty JSON array")
        payload = {
            "base_token": base_ops.base_token(args.base_token),
            "table_id": args.table_id,
            "as_identity": "user",
            "lark_payload": build_lark_payload(records),
        }
        if args.dry_run:
            print(json.dumps(base_ops.dry_run_response("record_batch_create", payload), ensure_ascii=False))
            return 0
        code, response = base_ops.execute_with_retry_or_pending("record_batch_create", payload)
        print(json.dumps(response, ensure_ascii=False))
        return code
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
