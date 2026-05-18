#!/usr/bin/env python3
"""
Clean old original render PNGs under /tmp/onion-ad.

Compressed JPGs, selection JSON, HTML pages, and accepted zip packages are kept
by default. The purpose is to prevent raw render PNGs from accumulating while
preserving operator-facing deliverables and audit metadata.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("/tmp/onion-ad")
DEFAULT_ORIGINAL_RETENTION_DAYS = 7


def is_original_render_png(path: Path) -> bool:
    if path.suffix.lower() != ".png":
        return False
    name = path.name.lower()
    if ".compressed-" in name:
        return False
    return True


def cleanup_originals(root: Path, retention_days: int, dry_run: bool = False) -> dict[str, Any]:
    root = root.expanduser().resolve()
    cutoff = time.time() - retention_days * 24 * 60 * 60
    deleted = []
    kept = 0
    if not root.exists():
        return {"ok": True, "root": str(root), "deleted": [], "kept": 0, "missing_root": True}

    for path in root.rglob("*"):
        if not path.is_file() or not is_original_render_png(path):
            continue
        if path.stat().st_mtime >= cutoff:
            kept += 1
            continue
        deleted.append({"path": str(path), "bytes": path.stat().st_size})
        if not dry_run:
            path.unlink()

    return {
        "ok": True,
        "root": str(root),
        "retention_days": retention_days,
        "dry_run": dry_run,
        "deleted": deleted,
        "deleted_count": len(deleted),
        "deleted_bytes": sum(item["bytes"] for item in deleted),
        "kept": kept,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean old original onion render PNGs.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    parser.add_argument("--original-retention-days", type=int, default=DEFAULT_ORIGINAL_RETENTION_DAYS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.original_retention_days < 1:
        print(json.dumps({"ok": False, "error": "original retention must be at least 1 day"}, ensure_ascii=False))
        return 2
    result = cleanup_originals(Path(args.root), args.original_retention_days, args.dry_run)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
