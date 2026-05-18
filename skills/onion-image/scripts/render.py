#!/usr/bin/env python3
"""
Render one onion ad image through LaoZhang's OpenAI-compatible Images API.

Single image mode is the production path used by the onion-image skills:

  python3 render.py \
    --prompt "<prompt>" \
    --size 1568x672 \
    --reference assets/logos/onion-logo-standard-001.png \
    --output <output-dir>/set1_img1.png

Use --validate-only to check prompt, aspect ratio, output path and reference
paths without requiring LAOZHANG_API_KEY or calling the paid API.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

DEFAULT_API_BASE = "https://api.laozhang.ai/v1"
MODEL = "gpt-image-2"
QUALITY = "medium"
OUTPUT_FORMAT = "png"
ENV_FILE = Path.home() / ".onion-ad" / ".env"
QUALITY_CHOICES = {"low", "medium", "high"}
SIZE_RE = re.compile(r"^([1-9]\d*)x([1-9]\d*)$")

# Edits API only supports the three official preset sizes plus auto. Generation
# can use exact 16:9 / 9:16 sizes.
ROUTES = {
    "1:1": {"generation_size": "1024x1024", "edit_size": "1024x1024"},
    "3:2": {"generation_size": "1536x1024", "edit_size": "1536x1024"},
    "16:9": {"generation_size": "2048x1152", "edit_size": "1536x1024"},
    "9:16": {
        "generation_size": "1152x2048",
        "generation_fallback_size": "1024x1536",
        "edit_size": "1024x1536",
    },
}


class SizeNotSupported(Exception):
    pass


def log(level: str, message: str) -> None:
    print(f"[{level}] {message}", file=sys.stderr)


def load_dotenv_if_exists(path: Path) -> bool:
    """Load KEY=VALUE lines without overriding existing environment values."""
    path = Path(path).expanduser()
    if not path.is_file():
        return False

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if not key or key in os.environ:
            continue
        if "你的" in value or "占位" in value or value in {"sk-xxx", "sk-your-key"}:
            continue
        os.environ[key] = value
    return True


def autoload_dotenv() -> None:
    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent
    candidates = [
        ENV_FILE,
        Path.cwd() / ".env",
        skill_dir / ".env",
        script_dir / ".env",
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if load_dotenv_if_exists(resolved):
            log("INFO", f"loaded env from {resolved}")
            return


def find_project_root(start: Path) -> Path:
    """Find the plugin root from a script path; fall back to cwd."""
    cur = start.resolve()
    while True:
        if (cur / ".claude-plugin").is_dir() and (cur / "skills").is_dir():
            return cur
        parent = cur.parent
        if parent == cur:
            return Path.cwd().resolve()
        cur = parent


def resolve_reference_path(path: str | Path, project_root: Path, skill_dir: Path) -> Path:
    """Resolve references from cwd, plugin root, or onion-image skill root."""
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()

    candidates = [
        (Path.cwd() / p).resolve(),
        (project_root / p).resolve(),
        (skill_dir / p).resolve(),
    ]

    path_text = str(path)
    if path_text.startswith("skills/onion-image/"):
        candidates.append((project_root / p).resolve())
    if path_text.startswith("assets/"):
        candidates.append((skill_dir / p).resolve())
    if path_text.startswith("shared/assets/"):
        candidates.append((skill_dir / Path(path_text.removeprefix("shared/assets/"))).resolve())

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]


def normalize_reference_item(item: object, index: int) -> dict:
    if isinstance(item, str):
        return {
            "path": item,
            "label": f"参考图{index}",
            "role": "参考图",
            "asset_id": None,
            "strict_label": False,
        }
    if isinstance(item, dict):
        path = item.get("path") or item.get("file") or item.get("src")
        if not path or not str(path).strip():
            raise ValueError(f"reference_images[{index - 1}] must include path")
        label = str(item.get("label") or f"参考图{index}").strip()
        if not label:
            raise ValueError(f"reference_images[{index - 1}] label must not be empty")
        return {
            "path": str(path),
            "label": label,
            "role": str(item.get("role") or item.get("prompt_role") or "参考图").strip(),
            "asset_id": item.get("asset_id"),
            "strict_label": bool(item.get("label")),
        }
    raise ValueError(f"reference_images[{index - 1}] must be a string path or object")


def normalize_reference_items(items: list[object]) -> list[dict]:
    normalized = [normalize_reference_item(item, index) for index, item in enumerate(items, start=1)]
    labels = [item["label"] for item in normalized]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        raise ValueError("duplicate reference labels: " + ", ".join(duplicates))
    return normalized


def validate_reference_labels(prompt: str, reference_items: list[dict]) -> None:
    missing = [
        item["label"]
        for item in reference_items
        if item.get("strict_label") and item["label"] not in prompt
    ]
    if missing:
        raise ValueError(
            "prompt must mention every explicitly labeled reference image: "
            + ", ".join(missing)
        )


def build_multipart(fields: dict[str, str], files: list[tuple[str, Path, bytes, str]]) -> tuple[str, bytes]:
    boundary = "----onionRender" + uuid.uuid4().hex
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode("ascii"))
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        parts.append(str(value).encode("utf-8"))
        parts.append(b"\r\n")

    for name, path, content, content_type in files:
        filename = path.name
        parts.append(f"--{boundary}\r\n".encode("ascii"))
        parts.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        parts.append(f"Content-Type: {content_type}\r\n\r\n".encode("ascii"))
        parts.append(content)
        parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode("ascii"))
    return f"multipart/form-data; boundary={boundary}", b"".join(parts)


def validate_size_label(size: str) -> str:
    size = str(size or "").strip().lower()
    match = SIZE_RE.match(size)
    if not match:
        raise ValueError("size must be formatted as WIDTHxHEIGHT, for example 1568x672")
    width = int(match.group(1))
    height = int(match.group(2))
    if width <= 0 or height <= 0:
        raise ValueError("size dimensions must be positive")
    return f"{width}x{height}"


def normalize_quality(value: str | None) -> str:
    quality = str(value or QUALITY).strip().lower()
    if quality not in QUALITY_CHOICES:
        raise ValueError(f"quality must be one of {', '.join(sorted(QUALITY_CHOICES))}")
    return quality


def build_generation_request(api_base: str, api_key: str, prompt: str, size: str, quality: str = QUALITY) -> urllib.request.Request:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "output_format": OUTPUT_FORMAT,
        "background": "opaque",
    }
    return urllib.request.Request(
        f"{api_base.rstrip('/')}/images/generations",
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def build_edit_request(
    api_base: str,
    api_key: str,
    prompt: str,
    reference_paths: list[Path],
    size: str,
    quality: str = QUALITY,
) -> urllib.request.Request:
    fields = {
        "model": MODEL,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "output_format": OUTPUT_FORMAT,
        "background": "opaque",
    }
    files = []
    for ref in reference_paths:
        content_type = mimetypes.guess_type(str(ref))[0] or "image/png"
        files.append(("image", ref, ref.read_bytes(), content_type))
    content_type, body = build_multipart(fields, files)
    return urllib.request.Request(
        f"{api_base.rstrip('/')}/images/edits",
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
        },
        data=body,
    )


def request_json(req: urllib.request.Request, retries: int) -> dict:
    last_error = ""
    waits = [1, 3, 9]
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {body[:500]}"
            lower = body.lower()
            if exc.code == 401:
                log("ERROR", "LAOZHANG_API_KEY invalid or expired")
                raise SystemExit(2)
            if exc.code == 402:
                log("ERROR", "LaoZhang API balance is insufficient")
                raise SystemExit(3)
            if exc.code in (400, 422):
                if "size" in lower and ("support" in lower or "invalid" in lower or "不支持" in body):
                    raise SizeNotSupported(body)
                if "moderation" in lower or "violat" in lower or "审核" in body:
                    log("ERROR", "moderation_blocked: adjust prompt and retry")
                    raise SystemExit(4)
                log("ERROR", last_error)
                raise SystemExit(4)
            if exc.code == 429 or 500 <= exc.code <= 599:
                if attempt < retries:
                    wait = waits[min(attempt - 1, len(waits) - 1)]
                    log("WARN", f"{last_error}; retrying in {wait}s ({attempt}/{retries})")
                    time.sleep(wait)
                    continue
            log("ERROR", last_error)
            raise SystemExit(3)
        except urllib.error.URLError as exc:
            last_error = f"network error: {exc}"
            if attempt < retries:
                wait = waits[min(attempt - 1, len(waits) - 1)]
                log("WARN", f"{last_error}; retrying in {wait}s ({attempt}/{retries})")
                time.sleep(wait)
                continue
            log("ERROR", last_error)
            raise SystemExit(3)
    log("ERROR", f"request failed after {retries} tries: {last_error}")
    raise SystemExit(3)


def save_image_from_response(body: dict, output_path: str | Path) -> Path:
    data = body.get("data") or []
    if not data:
        log("ERROR", f"unexpected response shape: {json.dumps(body, ensure_ascii=False)[:500]}")
        raise SystemExit(3)

    item = data[0]
    value = item.get("b64_json")
    if not value:
        log("ERROR", f"no b64_json in response item: {json.dumps(item, ensure_ascii=False)[:500]}")
        raise SystemExit(3)
    if value.startswith("data:"):
        value = value.split(",", 1)[1]
    value += "=" * ((4 - len(value) % 4) % 4)

    try:
        image_bytes = base64.b64decode(value)
    except Exception as exc:
        log("ERROR", f"b64 decode failed: {exc}")
        raise SystemExit(3)

    output = Path(output_path).expanduser()
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image_bytes)
    if output.stat().st_size <= 0:
        log("ERROR", f"empty output image: {output}")
        raise SystemExit(3)
    return output


def load_input(args: argparse.Namespace) -> dict:
    payload: dict = {}
    if args.input_json:
        payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    if args.prompt:
        payload["prompt"] = args.prompt
    if args.aspect_ratio:
        payload["aspect_ratio"] = args.aspect_ratio
    if args.size:
        payload["size"] = args.size
    if args.quality:
        payload["quality"] = args.quality
    references = list(payload.get("reference_images") or [])
    references.extend(args.reference or [])
    payload["reference_images"] = references
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input-json", help="JSON with prompt/reference_images/aspect_ratio or size")
    parser.add_argument("--prompt", help="Complete prompt text")
    parser.add_argument("--aspect-ratio", choices=sorted(ROUTES), help="1:1, 3:2, 16:9, or 9:16")
    parser.add_argument("--size", help="Explicit GPT image size, e.g. 1568x672. Overrides --aspect-ratio route size.")
    parser.add_argument("--quality", choices=sorted(QUALITY_CHOICES), default=QUALITY)
    parser.add_argument("--reference", action="append", default=[], help="Local reference image path; repeatable")
    parser.add_argument("--output", required=True, help="Output PNG path")
    parser.add_argument("--api-base", default=None, help=f"API base URL, default {DEFAULT_API_BASE}")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--validate-only", action="store_true", help="Validate without calling the API")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    autoload_dotenv()

    payload = load_input(args)
    prompt = str(payload.get("prompt") or "").strip()
    aspect_ratio = str(payload.get("aspect_ratio") or "").strip()
    explicit_size = str(payload.get("size") or "").strip()
    if not prompt:
        log("ERROR", "prompt is required")
        return 1
    try:
        quality = normalize_quality(payload.get("quality"))
        if explicit_size:
            size = validate_size_label(explicit_size)
            aspect_ratio_label = aspect_ratio if aspect_ratio in ROUTES else "custom"
            route = None
        else:
            if aspect_ratio not in ROUTES:
                log("ERROR", f"aspect_ratio must be one of {', '.join(sorted(ROUTES))}, or pass --size WIDTHxHEIGHT")
                return 1
            route = ROUTES[aspect_ratio]
            aspect_ratio_label = aspect_ratio
            size = ""
    except ValueError as exc:
        log("ERROR", str(exc))
        return 1

    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent
    project_root = find_project_root(script_dir)
    try:
        reference_items = normalize_reference_items(list(payload.get("reference_images", [])))
        validate_reference_labels(prompt, reference_items)
    except ValueError as exc:
        log("ERROR", str(exc))
        return 1
    reference_paths = [
        resolve_reference_path(item["path"], project_root=project_root, skill_dir=skill_dir)
        for item in reference_items
        if str(item["path"]).strip()
    ]
    missing = [str(path) for path in reference_paths if not path.is_file()]
    if missing:
        log("ERROR", "reference image not found: " + ", ".join(missing))
        return 1

    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()

    use_edits = bool(reference_paths)
    if not size:
        size = route["edit_size" if use_edits else "generation_size"]
    endpoint = "/images/edits" if use_edits else "/images/generations"
    metadata = {
        "valid": True,
        "filepath": str(output),
        "size_label": size,
        "size": size,
        "aspect_ratio": aspect_ratio_label,
        "model": MODEL,
        "quality": quality,
        "endpoint": endpoint,
        "reference_images": [item["path"] for item in reference_items],
        "reference_image_labels": [
            {
                "label": item["label"],
                "role": item["role"],
                "asset_id": item.get("asset_id"),
                "path": item["path"],
            }
            for item in reference_items
        ],
        "reference_images_resolved": [str(path) for path in reference_paths],
        "prompt_used": prompt,
    }

    if args.validate_only:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return 0

    api_key = os.environ.get("LAOZHANG_API_KEY")
    if not api_key:
        log("ERROR", "LAOZHANG_API_KEY is missing; configure ~/.onion-ad/.env")
        return 2
    api_base = args.api_base or os.environ.get("LAOZHANG_API_BASE", DEFAULT_API_BASE)

    log("INFO", f"rendering {aspect_ratio} size={size} endpoint={endpoint} refs={len(reference_paths)}")
    if use_edits:
        req = build_edit_request(api_base, api_key, prompt, reference_paths, size, quality)
        body = request_json(req, args.retries)
    else:
        req = build_generation_request(api_base, api_key, prompt, size, quality)
        try:
            body = request_json(req, args.retries)
        except SizeNotSupported:
            fallback = route.get("generation_fallback_size") if route else None
            if not fallback:
                raise
            log("WARN", f"size {size} rejected; retrying with fallback {fallback}")
            size = fallback
            metadata["size_label"] = size
            metadata["size"] = size
            req = build_generation_request(api_base, api_key, prompt, size, quality)
            body = request_json(req, args.retries)

    saved = save_image_from_response(body, output)
    metadata["filepath"] = str(saved)
    metadata["valid"] = True
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
