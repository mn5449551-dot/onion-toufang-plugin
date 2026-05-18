#!/usr/bin/env python3
"""
Clean old original render PNGs under the onion output root.

Compressed JPGs, selection JSON, HTML pages, and accepted zip packages are kept
by default. The purpose is to prevent raw render PNGs from accumulating while
preserving operator-facing deliverables and audit metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parents[2]
SHARED_SCRIPTS = PLUGIN_ROOT / "shared" / "scripts"
if str(SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS))

from runtime_paths import output_root  # noqa: E402


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
    parser.add_argument("--root", default=str(output_root()))
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
