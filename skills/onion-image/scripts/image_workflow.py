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
import os
from pathlib import Path
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parents[2]
SHARED_SCRIPTS = PLUGIN_ROOT / "shared" / "scripts"
if str(SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS))

from runtime_paths import request_output_dir  # noqa: E402
from write_selection_feedback import feedback_records_from_selection, selection_feedback_errors


ENV_FILE = Path.home() / ".onion-ad" / ".env"
PLACEHOLDER_KEY_MARKERS = ("你的", "占位", "sk-xxx", "sk-your-key", "your-key")


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return data


def load_dotenv_if_exists(path: Path) -> None:
    path = path.expanduser()
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_runtime_env(output_dir: Path) -> None:
    for candidate in (Path.home() / ".onion-ad" / ".env", Path.cwd() / ".env", output_dir / ".env"):
        load_dotenv_if_exists(candidate)


def api_key_ready() -> bool:
    value = str(os.environ.get("LAOZHANG_API_KEY") or "").strip()
    if not value:
        return False
    lowered = value.lower()
    return not any(marker in lowered for marker in PLACEHOLDER_KEY_MARKERS)


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
    marker = output_dir / "ui-reference-uploaded.json"
    if marker.is_file():
        return True
    reference_dir = output_dir / "ui-reference"
    if reference_dir.is_dir() and any(path.is_file() for path in reference_dir.iterdir()):
        return True
    references = (config or {}).get("reference_images") or []
    if isinstance(references, list):
        for item in references:
            value = item.get("path") if isinstance(item, dict) else item
            if value and Path(str(value)).expanduser().is_file():
                return True
    return False


def package_exists(request_id: str, output_dir: Path) -> bool:
    candidates = [
        output_dir / f"{request_id}-accepted-images.zip",
        output_dir / "accepted-images.zip",
    ]
    return any(path.is_file() for path in candidates) or any(output_dir.glob("*accepted*.zip"))


def request_id_errors(request_id: str, artifacts: list[tuple[str, dict[str, Any] | None]]) -> list[str]:
    errors = []
    for name, data in artifacts:
        if not data:
            continue
        artifact_request_id = data.get("request_id")
        if artifact_request_id and str(artifact_request_id) != request_id:
            errors.append(f"{name}.request_id={artifact_request_id} does not match {request_id}")
    return errors


def config_errors(config: dict[str, Any] | None) -> list[str]:
    if not config:
        return []
    errors = []
    placements = config.get("placements")
    if not isinstance(placements, list) or not placements:
        errors.append("image-config-result.json must include non-empty placements")
    elif not any(isinstance(item, dict) and item.get("render_size") for item in placements):
        errors.append("placements must include render_size")
    generation_mode = str(config.get("generation_mode") or config.get("generationMode") or "explore")
    if generation_mode == "iterate":
        role = str(config.get("uploaded_image_role") or config.get("uploadedImageRole") or "").strip()
        if role in {"", "unknown"}:
            errors.append("generation_mode=iterate requires uploaded_image_role other than unknown")
        iteration_mode = str(config.get("iteration_mode") or config.get("iterationMode") or "").strip()
        if iteration_mode not in {"tweak", "expand_similar", "reframe"}:
            errors.append("generation_mode=iterate requires iteration_mode=tweak|expand_similar|reframe")
    return errors


def build_status(request_id: str, output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.expanduser().resolve()
    load_runtime_env(output_dir)
    config_path = output_dir / "image-config-result.json"
    sets_path = output_dir / "image-sets.json"
    selection_path = output_dir / "image-selection-result.json"
    feedback_result_path = output_dir / "image-feedback-result.json"
    write_result_path = output_dir / "image-write-result.json"

    config = load_json(config_path)
    image_sets = load_json(sets_path)
    selection = load_json(selection_path)
    write_result = load_json(write_result_path)
    accepted = accepted_schemes(selection)
    feedback_errors = selection_feedback_errors(selection) if selection else []
    feedback_records = feedback_records_from_selection(selection) if selection else []

    artifacts = {
        "output_dir": str(output_dir),
        "config": str(config_path) if config_path.is_file() else None,
        "image_sets": str(sets_path) if sets_path.is_file() else None,
        "selection_result": str(selection_path) if selection_path.is_file() else None,
        "feedback_result": str(feedback_result_path) if feedback_result_path.is_file() else None,
        "write_result": str(write_result_path) if write_result_path.is_file() else None,
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

    stale_errors = request_id_errors(
        request_id,
        [
            ("image-config-result.json", config),
            ("image-sets.json", image_sets),
            ("image-selection-result.json", selection),
        ],
    )
    if stale_errors:
        return {
            **base,
            "stage": "invalid_artifacts",
            "errors": stale_errors,
            "next_action": "当前输出目录里的 request_id 与本轮不一致。停止续跑，确认 --request-id 和 --output-dir 是否匹配，避免使用旧文件。",
        }

    invalid_config = config_errors(config)
    if invalid_config:
        return {
            **base,
            "stage": "invalid_config",
            "errors": invalid_config,
            "next_action": "image-config-result.json 缺少有效 placements/render_size，或迭代配置缺少 uploaded_image_role / iteration_mode。请重新打开配置页保存配置，不要直接渲染。",
        }

    if ui_reference_required(config) and not ui_reference_satisfied(config, output_dir):
        return {
            **base,
            "stage": "needs_ui_reference_upload",
            "next_action": "提醒用户回到 Codex 对话上传截图（洋葱 APP/功能界面截图），或确认改成弱化/模糊屏幕内容。",
        }

    if not has_rendered_sets(image_sets):
        if not api_key_ready():
            return {
                **base,
                "stage": "needs_api_key",
                "next_action": "LAOZHANG_API_KEY 缺失或仍是占位符。先运行 onion-help 环境检查，或补 ~/.onion-ad/.env 后再渲染。",
            }
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

    if feedback_errors:
        return {
            **base,
            "stage": "invalid_selection_feedback",
            "can_prompt": True,
            "errors": feedback_errors,
            "next_action": "选择页里有不完整的不采纳反馈。请用户回到 image-selection.html，把不采纳原因改为固定规则 / 主观感受并填写文字，或选择跳过反馈后重新提交。",
        }

    if feedback_records and not feedback_result_path.is_file():
        return {
            **base,
            "stage": "needs_feedback_write",
            "can_prompt": True,
            "feedback_count": len(feedback_records),
            "next_action": "先运行 scripts/write_selection_feedback.py 把 rejected_schemes 里的固定规则 / 主观感受写入 feedbacks，再继续打包 accepted_schemes。",
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

    if write_result_path.is_file() and write_result and write_result.get("ok"):
        return {
            **base,
            "stage": "complete",
            "can_prompt": True,
            "can_package": True,
            "next_action": "本轮已有 image-write-result.json；如需继续生成，创建新 request_id 或追加新批次后重新检查。",
        }

    if write_result_path.is_file() and write_result and write_result.get("record_id"):
        return {
            **base,
            "stage": "needs_attachment_resume",
            "can_prompt": True,
            "can_package": True,
            "record_id": write_result.get("record_id"),
            "next_action": "image_groups 记录已创建但附件上传未完成；resume by rerunning shared/scripts/write_image_group.py with the same --write-result，脚本会复用已有 record_id，不要重新创建图组记录。",
        }

    if write_result_path.is_file():
        return {
            **base,
            "stage": "invalid_write_result",
            "can_prompt": True,
            "can_package": True,
            "next_action": "image-write-result.json 存在但缺少 ok=true 或 record_id。先人工检查该文件和飞书记录，避免重复创建图组。",
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
    return request_output_dir(request_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect onion image workflow state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Print current workflow stage as JSON.")
    status.add_argument("--request-id", required=True)
    status.add_argument("--output-dir", help="Defaults to the portable onion output root for this request.")

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
