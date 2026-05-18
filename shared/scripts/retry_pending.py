from __future__ import annotations

import argparse
import json
from typing import List

import base_ops


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retry safe pending onion Base operations.")
    parser.add_argument("--force-ambiguous", action="store_true")
    args = parser.parse_args(argv)

    stats = base_ops.retry_items(force_ambiguous=args.force_ambiguous)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
