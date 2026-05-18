#!/usr/bin/env python3
"""
Package accepted image schemes from image-selection-result.json into one zip.

The zip is a local delivery artifact for operators. It contains only accepted
scheme images, with compressed JPGs by default. A manifest JSON is written next
to the zip for traceability, not inside the operator-facing zip.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
IMAGE_COMPRESS_SCRIPT = SCRIPT_DIR / "image_compress.py"
DEFAULT_TARGET_KB = 200
SAFE_COMPONENT_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("selection result must be a JSON object")
    return data


def resolve_image_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"image not found: {path}")
    return path


def scheme_image_paths(scheme: dict[str, Any], base_dir: Path) -> list[Path]:
    if isinstance(scheme.get("thumb"), list):
        values = scheme["thumb"]
    elif isinstance(scheme.get("images"), list):
        values = [item.get("path") if isinstance(item, dict) else item for item in scheme["images"]]
    else:
        values = []
    paths = [resolve_image_path(str(value), base_dir) for value in values if value]
    if not paths:
        raise ValueError(f"accepted scheme {scheme.get('set_id') or scheme.get('id')} has no images")
    return paths


def parse_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def scheme_export_config(scheme: dict[str, Any], default_target_kb: int) -> dict[str, int | None]:
    meta = scheme.get("meta") if isinstance(scheme.get("meta"), dict) else {}
    placement = scheme.get("placement") if isinstance(scheme.get("placement"), dict) else {}
    target_kb = parse_int(scheme.get("target_kb")) or parse_int(meta.get("target_kb")) or parse_int(meta.get("目标KB")) or default_target_kb
    target_width = (
        parse_int(scheme.get("target_width"))
        or parse_int(meta.get("target_width"))
        or parse_int(meta.get("目标宽度"))
        or parse_int(placement.get("target_width"))
    )
    target_height = (
        parse_int(scheme.get("target_height"))
        or parse_int(meta.get("target_height"))
        or parse_int(meta.get("目标高度"))
        or parse_int(placement.get("target_height"))
    )
    return {"target_kb": target_kb, "target_width": target_width, "target_height": target_height}


def compressed_path_for(source: Path, cache_dir: Path, set_id: str, target_kb: int, target_width: int | None = None, target_height: int | None = None) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    size_suffix = f".{target_width}x{target_height}" if target_width and target_height else ""
    return cache_dir / f"{safe_component(set_id, 'set')}-{safe_component(source.stem, 'image')}{size_suffix}.compressed-{target_kb}kb.jpg"


def compress_image(source: Path, output: Path, target_kb: int, target_width: int | None = None, target_height: int | None = None) -> None:
    command = [
            sys.executable,
            str(IMAGE_COMPRESS_SCRIPT),
            str(source),
            str(output),
            "--target-kb",
            str(target_kb),
        ]
    if target_width and target_height:
        command.extend(["--target-width", str(target_width), "--target-height", str(target_height)])
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "image compression failed").strip())


def safe_component(value: Any, fallback: str) -> str:
    text = str(value or "").strip().lower()
    text = SAFE_COMPONENT_PATTERN.sub("-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-._")
    return text or fallback


def archive_dir_name(position: int, set_id: str) -> str:
    return f"set{position:02d}_{safe_component(set_id, f'set{position:02d}')}"


def archive_file_name(
    set_position: int,
    image_index: int,
    suffix: str,
    target_kb: int | None = None,
    target_width: int | None = None,
    target_height: int | None = None,
) -> str:
    parts = [f"set{set_position:02d}", f"img{image_index:02d}"]
    if target_width and target_height:
        parts.append(f"{target_width}x{target_height}")
    if target_kb:
        parts.append(f"{target_kb}kb")
    normalized_suffix = suffix.lower() or ".jpg"
    return "_".join(parts) + normalized_suffix


def manifest_path_for(output: Path) -> Path:
    return output.with_name(f"{output.stem}-manifest.json")


def package_accepted_images(
    selection_result: Path,
    output: Path | None = None,
    target_kb: int = DEFAULT_TARGET_KB,
    compress: bool = True,
) -> dict[str, Any]:
    base_dir = selection_result.resolve().parent
    data = load_json(selection_result)
    accepted = data.get("accepted_schemes") or []
    if not isinstance(accepted, list) or not accepted:
        raise ValueError("selection result has no accepted_schemes to package")

    request_id = str(data.get("request_id") or base_dir.name)
    output = output or (base_dir / f"{request_id}-accepted-images.zip")
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = output.parent / "accepted-package-assets"
    manifest_path = manifest_path_for(output)

    package_manifest: dict[str, Any] = {
        "request_id": request_id,
        "zip": str(output),
        "target_kb": target_kb if compress else None,
        "compressed": compress,
        "accepted_count": len(accepted),
        "schemes": [],
    }

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for position, scheme in enumerate(accepted, start=1):
            set_id = str(scheme.get("set_id") or scheme.get("id") or f"set{position}")
            archive_dir = archive_dir_name(position, set_id)
            export = scheme_export_config(scheme, target_kb)
            scheme_target_kb = int(export["target_kb"] or target_kb)
            target_width = export["target_width"]
            target_height = export["target_height"]
            scheme_entry = {
                "set_id": set_id,
                "meta": scheme.get("meta") or {},
                "source": scheme.get("source") or {},
                "export": export,
                "files": [],
            }
            for image_index, source in enumerate(scheme_image_paths(scheme, base_dir), start=1):
                if compress:
                    packaged = compressed_path_for(source, cache_dir, set_id, scheme_target_kb, target_width, target_height)
                    if not packaged.exists():
                        compress_image(source, packaged, scheme_target_kb, target_width, target_height)
                else:
                    packaged = source
                arcname = f"{archive_dir}/{archive_file_name(position, image_index, packaged.suffix, scheme_target_kb if compress else None, target_width, target_height)}"
                archive.write(packaged, arcname)
                scheme_entry["files"].append(
                    {
                        "index": image_index,
                        "source": str(source),
                        "packaged": str(packaged),
                        "zip_path": arcname,
                    }
                )
            package_manifest["schemes"].append(scheme_entry)
    manifest_path.write_text(json.dumps(package_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "zip": str(output),
        "manifest_path": str(manifest_path),
        "accepted_count": len(accepted),
        "compressed": compress,
        "target_kb": target_kb if compress else None,
        "manifest": package_manifest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package accepted onion image schemes into one zip.")
    parser.add_argument("--selection-result", required=True, help="Path to image-selection-result.json")
    parser.add_argument("--output", help="Output zip path; defaults to <request_id>-accepted-images.zip beside selection result")
    parser.add_argument("--target-kb", type=int, default=DEFAULT_TARGET_KB)
    parser.add_argument("--no-compress", action="store_true", help="Package original files instead of compressed JPGs")
    args = parser.parse_args(argv)

    try:
        result = package_accepted_images(
            selection_result=Path(args.selection_result),
            output=Path(args.output) if args.output else None,
            target_kb=args.target_kb,
            compress=not args.no_compress,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
