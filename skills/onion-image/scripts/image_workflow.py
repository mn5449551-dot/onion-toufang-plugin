#!/usr/bin/env python3
"""
Inspect an onion image request directory and tell the agent what is allowed next.

This script is intentionally small: it does not render, package, or write Base.
It prevents the common workflow skips by turning local artifacts into explicit
gates before paid rendering and before Feishu writes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


DEFAULT_ROOT = Path("/tmp/onion-ad")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return data


def non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def has_rendered_sets(data: dict[str, Any] | None) -> bool:
    if not data:
        return False
    return non_empty_list(data.get("sets")) or non_empty_list(data.get("schemes"))


def accepted_schemes(data: dict[str, Any] | None) -> list[Any]:
    if not data:
        return []
    value = data.get("accepted_schemes")
    return value if isinstance(value, list) else []


def ui_reference_required(config: dict[str, Any] | None) -> bool:
    if not config:
        return False
    return bool(config.get("screen_ui_reference_required") or config.get("ui_reference_required"))


def ui_reference_satisfied(config: dict[str, Any] | None, output_dir: Path) -> bool:
    if not ui_reference_required(config):
        return True
    status = str((config or {}).get("ui_reference_upload_status") or "").strip()
    if status in {"uploaded", "provided", "satisfied"}:
        return True
    marker = output_dir / "ui-reference-uploaded.json"
    if marker.is_file():
        return True
    reference_dir = output_dir / "ui-reference"
    return reference_dir.is_dir() and any(path.is_file() for path in reference_dir.iterdir())


def package_exists(request_id: str, output_dir: Path) -> bool:
    candidates = [
        output_dir / f"{request_id}-accepted-images.zip",
        output_dir / "accepted-images.zip",
    ]
    return any(path.is_file() for path in candidates) or any(output_dir.glob("*accepted*.zip"))


def build_status(request_id: str, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.expanduser().resolve()
    config_path = output_dir / "image-config-result.json"
    sets_path = output_dir / "image-sets.json"
    selection_path = output_dir / "image-selection-result.json"

    config = load_json(config_path)
    image_sets = load_json(sets_path)
    selection = load_json(selection_path)
    accepted = accepted_schemes(selection)

    artifacts = {
        "output_dir": str(output_dir),
        "config": str(config_path) if config_path.is_file() else None,
        "image_sets": str(sets_path) if sets_path.is_file() else None,
        "selection_result": str(selection_path) if selection_path.is_file() else None,
        "accepted_package": None,
    }

    for candidate in [output_dir / f"{request_id}-accepted-images.zip", output_dir / "accepted-images.zip", *output_dir.glob("*accepted*.zip")]:
        if candidate.is_file():
            artifacts["accepted_package"] = str(candidate.resolve())
            break

    base = {
        "ok": True,
        "request_id": request_id,
        "artifacts": artifacts,
        "can_prompt": False,
        "can_render": False,
        "can_package": False,
        "can_write_base": False,
    }

    if not config:
        return {
            **base,
            "stage": "needs_config",
            "next_action": "启动 scripts/interactive_server.py 打开 /image-config，让用户保存本轮图片配置。",
        }

    if ui_reference_required(config) and not ui_reference_satisfied(config, output_dir):
        return {
            **base,
            "stage": "needs_ui_reference_upload",
            "next_action": "提醒用户回到 Codex 对话上传截图（洋葱 APP/功能界面截图），或确认改成弱化/模糊屏幕内容。",
        }

    if not has_rendered_sets(image_sets):
        return {
            **base,
            "stage": "ready_to_render",
            "can_prompt": True,
            "can_render": True,
            "next_action": "生成 prompt，先运行 render.py --validate-only，再按配置里的 render_size 渲染，并把结果 POST 到 /api/image-sets。",
        }

    if not selection:
        return {
            **base,
            "stage": "needs_selection",
            "can_prompt": True,
            "next_action": "构建或打开 image-selection.html，让用户完成采纳/不采纳标注并提交。",
        }

    if not accepted:
        return {
            **base,
            "stage": "blocked_no_accepted_schemes",
            "can_prompt": True,
            "next_action": "选择结果里没有 accepted_schemes，不能打包或写 Base；请用户在选择页至少采纳一套，或明确全部废弃。",
        }

    if not package_exists(request_id, output_dir):
        return {
            **base,
            "stage": "needs_package",
            "can_prompt": True,
            "can_package": True,
            "next_action": "先运行 scripts/package_accepted_images.py 打包 accepted_schemes，再写 Base。",
        }

    write_result = output_dir / "image-write-result.json"
    if write_result.is_file():
        return {
            **base,
            "stage": "complete",
            "can_prompt": True,
            "can_package": True,
            "next_action": "本轮已有 image-write-result.json；如需继续生成，创建新 request_id 或追加新批次后重新检查。",
        }

    return {
        **base,
        "stage": "ready_to_write_base",
        "can_prompt": True,
        "can_package": True,
        "can_write_base": True,
        "next_action": "调用 shared/scripts/write_image_group.py 写 image_groups 并上传压缩附件；成功后写 image-write-result.json 或继续清理原始 PNG。",
    }


def default_output_dir(request_id: str) -> Path:
    return DEFAULT_ROOT / request_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect onion image workflow state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Print current workflow stage as JSON.")
    status.add_argument("--request-id", required=True)
    status.add_argument("--output-dir", help="Defaults to /tmp/onion-ad/<request-id>")

    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir(args.request_id)

    try:
        payload = build_status(args.request_id, output_dir)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
