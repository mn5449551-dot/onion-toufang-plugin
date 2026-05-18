from __future__ import annotations

import argparse
import json
import sys
from typing import List

import base_ops


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update Base record status through lark-cli record-batch-update.")
    parser.add_argument("--base-token")
    parser.add_argument("--table-id", required=True)
    parser.add_argument("--record-id", action="append", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--status-field", default="状态")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = {
            "base_token": base_ops.base_token(args.base_token),
            "table_id": args.table_id,
            "as_identity": "user",
            "lark_payload": {
                "record_id_list": args.record_id,
                "patch": {args.status_field: args.status},
            },
        }
        if args.dry_run:
            print(json.dumps(base_ops.dry_run_response("record_batch_update", payload), ensure_ascii=False))
            return 0
        code, response = base_ops.execute_with_retry_or_pending("record_batch_update", payload)
        print(json.dumps(response, ensure_ascii=False))
        return code
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
