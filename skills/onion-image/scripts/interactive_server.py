#!/usr/bin/env python3
"""
Local interaction server for onion-image.

This is the half-automatic bridge for Codex/Claude runtimes that cannot show a
native choice card. It serves a deterministic image configuration page, writes
the submitted result to JSON, and can also serve generated selection pages and
their local image assets from the same output directory.
"""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import posixpath
import socket
import sys
from typing import Any
from urllib.parse import parse_qs, urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
PLUGIN_ROOT = SKILL_DIR.parents[1]
DEFAULT_CHANNEL_RULES = SKILL_DIR / "config" / "channel-placement-rules.json"
ASSET_MANIFEST = SKILL_DIR / "assets" / "asset-manifest.json"
FONT_DIR = SKILL_DIR / "assets" / "font-references"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from build_selection_page import normalize_sets  # noqa: E402

IMAGE_SETS_FILE = "image-sets.json"


FALLBACK_SLOTS = [
    {
        "id": "oppo_app_store_single_16_9_big",
        "platform": "OPPO",
        "name": "富媒体 - 横版大图",
        "channel": "应用商店",
        "imageForm": "单图",
        "ratio": "16:9",
        "width": 1280,
        "height": 720,
        "maxFileSizeKb": 150,
        "notes": "可加 Logo",
    },
    {
        "id": "oppo_app_store_double_9_16",
        "platform": "OPPO",
        "name": "富媒体 - 横版两图",
        "channel": "应用商店",
        "imageForm": "双图",
        "ratio": "9:16",
        "width": 474,
        "height": 768,
        "maxFileSizeKb": 150,
    },
    {
        "id": "oppo_app_store_triple_3_2",
        "platform": "OPPO",
        "name": "富媒体 - 横版三图",
        "channel": "应用商店",
        "imageForm": "三图",
        "ratio": "3:2",
        "width": 320,
        "height": 210,
        "maxFileSizeKb": 100,
    },
    {
        "id": "oppo_app_store_single_16_9_banner",
        "platform": "OPPO",
        "name": "竞价 banner",
        "channel": "应用商店",
        "imageForm": "单图",
        "ratio": "16:9",
        "width": 1280,
        "height": 720,
        "maxFileSizeKb": 150,
        "notes": "不加 Logo",
    },
    {
        "id": "vivo_app_store_triple_9_16",
        "platform": "vivo",
        "name": "商店搜索 - 首位三图",
        "channel": "应用商店",
        "imageForm": "三图",
        "ratio": "9:16",
        "width": 1080,
        "height": 1920,
        "maxFileSizeKb": 150,
    },
    {
        "id": "vivo_app_store_single_root_2_1",
        "platform": "vivo",
        "name": "搜索富媒体 - 单图文",
        "channel": "应用商店",
        "imageForm": "单图",
        "ratio": "16:9",
        "width": 202,
        "height": 142,
        "maxFileSizeKb": 50,
    },
    {
        "id": "vivo_app_store_triple_3_2",
        "platform": "vivo",
        "name": "搜索富媒体 - 三图",
        "channel": "应用商店",
        "imageForm": "三图",
        "ratio": "3:2",
        "width": 320,
        "height": 211,
        "maxFileSizeKb": 80,
    },
    {
        "id": "vivo_app_store_single_16_11",
        "platform": "vivo",
        "name": "顶部 banner",
        "channel": "应用商店",
        "imageForm": "单图",
        "ratio": "16:9",
        "width": 720,
        "height": 498,
        "maxFileSizeKb": 150,
    },
    {
        "id": "xiaomi_app_store_single_16_9",
        "platform": "小米",
        "name": "搜索大图 / 二图 / 横版三图",
        "channel": "应用商店",
        "imageForm": "单图",
        "ratio": "16:9",
        "width": 960,
        "height": 540,
        "maxFileSizeKb": 500,
    },
    {
        "id": "xiaomi_app_store_triple_1_1",
        "platform": "小米",
        "name": "搜索三图",
        "channel": "应用商店",
        "imageForm": "三图",
        "ratio": "1:1",
        "width": 320,
        "height": 320,
        "maxFileSizeKb": 300,
    },
    {
        "id": "xiaomi_app_store_single_16_9_rich",
        "platform": "小米",
        "name": "富媒体大图",
        "channel": "应用商店",
        "imageForm": "单图",
        "ratio": "16:9",
        "width": 960,
        "height": 540,
        "maxFileSizeKb": 500,
    },
    {
        "id": "passthrough_information_feed_single_original",
        "platform": "原图直出",
        "name": "信息流原图直出",
        "channel": "信息流",
        "imageForm": "单图",
        "ratio": "1:1",
        "width": None,
        "height": None,
        "maxFileSizeKb": 999999,
    },
    {
        "id": "passthrough_learning_device_single_original",
        "platform": "原图直出",
        "name": "学习机单图原图直出",
        "channel": "学习机",
        "imageForm": "单图",
        "ratio": "1:1",
        "width": None,
        "height": None,
        "maxFileSizeKb": 999999,
    },
    {
        "id": "passthrough_learning_device_double_original",
        "platform": "原图直出",
        "name": "学习机双图原图直出",
        "channel": "学习机",
        "imageForm": "双图",
        "ratio": "1:1",
        "width": None,
        "height": None,
        "maxFileSizeKb": 999999,
    },
    {
        "id": "passthrough_learning_device_triple_original",
        "platform": "原图直出",
        "name": "学习机三图原图直出",
        "channel": "学习机",
        "imageForm": "三图",
        "ratio": "1:1",
        "width": None,
        "height": None,
        "maxFileSizeKb": 999999,
    },
]


RATIO_MAP = {
    "r_1_1": "1:1",
    "r_3_2": "3:2",
    "r_16_9": "16:9",
    "r_9_16": "9:16",
    "original": "1:1",
}

CHANNEL_MAP = {
    "app_store": "应用商店",
    "information_feed": "信息流",
    "learning_device": "学习机",
}

FORM_MAP = {
    "single": "单图",
    "double": "双图",
    "triple": "三图",
}


def html_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def find_free_port(preferred: int) -> int:
    if preferred:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", preferred)) != 0:
                return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def load_platform_slots(path: Path | None = None) -> list[dict[str, Any]]:
    source = path or DEFAULT_CHANNEL_RULES
    if not source or not source.exists():
        return FALLBACK_SLOTS

    data = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(data.get("placements"), list):
        slots = [normalize_channel_placement(slot) for slot in data["placements"]]
        return slots or FALLBACK_SLOTS

    slots: list[dict[str, Any]] = []
    for platform in data.get("platforms", []):
        platform_name = platform.get("name") or platform.get("id") or "其他"
        for slot in platform.get("slots", []):
            ratio = RATIO_MAP.get(slot.get("sourceRatio") or slot.get("targetRatio"), slot.get("targetRatio") or "1:1")
            if str(ratio).startswith("custom_"):
                ratio = slot.get("sourceRatio") and RATIO_MAP.get(slot["sourceRatio"], "16:9") or "16:9"
            target_width = slot.get("targetWidth")
            target_height = slot.get("targetHeight")
            slots.append(
                normalize_channel_placement(
                    {
                        "id": slot.get("id"),
                        "category": CHANNEL_MAP.get(slot.get("channel"), slot.get("channel") or "其他"),
                        "platform": platform_name,
                        "sub_channel": "",
                        "placement": slot.get("name"),
                        "name": slot.get("name"),
                        "image_form": FORM_MAP.get(slot.get("imageForm"), slot.get("imageForm") or "单图"),
                        "image_count": {"单图": 1, "双图": 2, "三图": 3}.get(FORM_MAP.get(slot.get("imageForm"), ""), 1),
                        "target_width": target_width,
                        "target_height": target_height,
                        "target_size": f"{target_width}x{target_height}" if target_width and target_height else "",
                        "target_ratio": ratio,
                        "render_width": target_width,
                        "render_height": target_height,
                        "render_size": f"{target_width}x{target_height}" if target_width and target_height else "",
                        "directness": "direct",
                        "postprocess": "resize",
                        "max_file_size_kb": slot.get("maxFileSizeKb"),
                        "logo_policy": "forbidden" if "不加" in str(slot.get("notes") or "") else "optional",
                        "cta_policy": "optional" if CHANNEL_MAP.get(slot.get("channel")) == "信息流" else "forbidden",
                        "enabled": True,
                        "disabled_reason": "",
                        "notes": slot.get("notes"),
                    }
                )
            )
    return slots or FALLBACK_SLOTS


def normalize_channel_placement(slot: dict[str, Any]) -> dict[str, Any]:
    category = slot.get("category") or slot.get("channel") or "其他"
    target_width = slot.get("target_width") or slot.get("width")
    target_height = slot.get("target_height") or slot.get("height")
    render_width = slot.get("render_width") or target_width
    render_height = slot.get("render_height") or target_height
    target_size = slot.get("target_size") or (f"{target_width}x{target_height}" if target_width and target_height else "")
    render_size = slot.get("render_size") or (f"{render_width}x{render_height}" if render_width and render_height else "")
    image_form = slot.get("image_form") or slot.get("imageForm") or "单图"
    max_kb = slot.get("max_file_size_kb", slot.get("maxFileSizeKb"))
    return {
        "id": slot.get("id"),
        "category": category,
        "channel": category,
        "platform": slot.get("platform") or "其他",
        "sub_channel": slot.get("sub_channel") or "",
        "name": slot.get("name") or slot.get("placement") or "通用",
        "placement": slot.get("placement") or slot.get("name") or "通用",
        "imageForm": image_form,
        "image_form": image_form,
        "image_count": int(slot.get("image_count") or {"单图": 1, "双图": 2, "三图": 3}.get(str(image_form), 1)),
        "ratio": slot.get("target_ratio") or slot.get("ratio") or "",
        "target_ratio": slot.get("target_ratio") or slot.get("ratio") or "",
        "width": target_width,
        "height": target_height,
        "target_width": target_width,
        "target_height": target_height,
        "target_size": target_size,
        "render_width": render_width,
        "render_height": render_height,
        "render_size": render_size,
        "maxFileSizeKb": max_kb,
        "max_file_size_kb": max_kb,
        "format": slot.get("format") or "",
        "directness": slot.get("directness") or "unknown",
        "directness_label": slot.get("directness_label") or "",
        "postprocess": slot.get("postprocess") or "",
        "logo_policy": slot.get("logo_policy") or "optional",
        "cta_policy": slot.get("cta_policy") or "forbidden",
        "enabled": bool(slot.get("enabled", True)),
        "disabled_reason": slot.get("disabled_reason") or "",
        "notes": slot.get("notes") or "",
        "source": slot.get("source") or "",
    }


def normalize_desired_image_form(context: dict[str, Any]) -> str:
    for key in ("image_form", "imageForm", "图片形式", "form"):
        value = str(context.get(key) or "").strip()
        if not value:
            continue
        lowered = value.lower()
        if value in {"单图", "双图", "三图"}:
            return value
        if lowered in {"single", "single_image", "one"} or "单" in value:
            return "单图"
        if lowered in {"double", "two", "two_images"} or "双" in value:
            return "双图"
        if lowered in {"triple", "three", "three_images"} or "三" in value:
            return "三图"
    return ""


def apply_context_image_form(slots: list[dict[str, Any]], desired_form: str) -> list[dict[str, Any]]:
    if not desired_form:
        return slots
    constrained = []
    for slot in slots:
        item = dict(slot)
        slot_form = item.get("imageForm") or item.get("image_form")
        if slot_form and slot_form != desired_form and item.get("enabled", True):
            item["enabled"] = False
            item["disabled_reason"] = f"本次图片形式为{desired_form}，该版位是{slot_form}"
        constrained.append(item)
    return constrained


def slots_by_id(path: Path | None = None) -> dict[str, dict[str, Any]]:
    return {str(slot["id"]): slot for slot in load_platform_slots(path) if slot.get("id")}


def load_ip_options(manifest_path: Path = ASSET_MANIFEST) -> list[dict[str, Any]]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    options = [
        {"value": "不用", "label": "不用 IP", "asset_id": "", "path": "", "thumb": "", "random": False},
        {"value": "随机", "label": "随机 IP", "asset_id": "__random_ip__", "path": "", "thumb": "", "random": True},
    ]
    for asset in data.get("assets", []):
        if asset.get("kind") != "ip":
            continue
        stage = asset.get("stage_display_name") or asset.get("stage")
        variant = asset.get("variant_display_name") or asset.get("variant")
        suffix = " / ".join([str(x) for x in [stage, variant] if x])
        label = asset.get("asset_name_zh") or f"{asset.get('display_name')}（{suffix}）"
        options.append(
            {
                "value": asset.get("display_name"),
                "label": label,
                "asset_id": asset.get("asset_id"),
                "path": asset.get("path"),
                "thumb": f"/skill-assets/{asset.get('path')}" if asset.get("path") else "",
                "random": False,
            }
        )
    return options


def load_logo_options(manifest_path: Path = ASSET_MANIFEST) -> list[dict[str, Any]]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    options = [{"value": "不用", "label": "不用 Logo", "asset_id": "", "path": "", "thumb": ""}]
    for asset in data.get("assets", []):
        if asset.get("kind") != "logo":
            continue
        options.append(
            {
                "value": asset.get("display_name"),
                "label": asset.get("display_name"),
                "asset_id": asset.get("asset_id"),
                "path": asset.get("path"),
                "thumb": f"/skill-assets/{asset.get('path')}" if asset.get("path") else "",
            }
        )
    return options


def load_font_options(font_dir: Path = FONT_DIR) -> list[dict[str, str]]:
    fonts = sorted(font_dir.glob("*.png"))
    return [
        {
            "label": path.stem,
            "asset_id": f"font.{path.stem.replace('字体参考-', 'ref.')}",
            "path": f"assets/font-references/{path.name}",
        }
        for path in fonts
    ]


def build_config_payload(
    request_id: str,
    context: dict[str, Any] | None = None,
    platform_rules: Path | None = None,
) -> dict[str, Any]:
    context = context or {}
    desired_form = normalize_desired_image_form(context)
    slots = apply_context_image_form(load_platform_slots(platform_rules), desired_form)
    categories = []
    for slot in slots:
        category = slot.get("category") or slot.get("channel")
        if category and category not in categories:
            categories.append(category)
    return {
        "request_id": request_id,
        "context": context,
        "slots": slots,
        "desiredImageForm": desired_form,
        "ipOptions": load_ip_options(),
        "fontOptions": load_font_options(),
        "logoOptions": load_logo_options(),
        "categories": categories or ["应用商店", "信息流", "学习机"],
    }


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def image_sets_payload(output_dir: Path, request_id: str) -> dict[str, Any]:
    path = output_dir / IMAGE_SETS_FILE
    data = read_json_file(path, {"request_id": request_id, "sets": []})
    if isinstance(data, list):
        data = {"request_id": request_id, "sets": data}
    data.setdefault("request_id", request_id)
    data.setdefault("sets", [])
    return data


def merge_image_sets(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item.get("set_id")): dict(item) for item in existing if item.get("set_id")}
    ordered_ids = [str(item.get("set_id")) for item in existing if item.get("set_id")]
    for item in incoming:
        set_id = str(item.get("set_id"))
        if set_id not in by_id:
            ordered_ids.append(set_id)
        by_id[set_id] = dict(item)
    return [by_id[set_id] for set_id in ordered_ids if set_id in by_id]


def update_image_sets(output_dir: Path, request_id: str, body: dict[str, Any]) -> dict[str, Any]:
    mode = body.get("mode") or "append"
    _, normalized = normalize_sets(body, output_dir)
    current = image_sets_payload(output_dir, request_id)
    if mode == "replace":
        sets = normalized
    else:
        sets = merge_image_sets(current.get("sets") or [], normalized)
    result = {"request_id": str(body.get("request_id") or request_id), "sets": sets}
    atomic_write_json(output_dir / IMAGE_SETS_FILE, result)
    return result


def normalize_config_result(body: dict[str, Any], slot_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    placement_ids = body.get("placement_ids") or body.get("selectedSlotIds") or []
    if not placement_ids and body.get("slot_id"):
        placement_ids = [body["slot_id"]]
    if not isinstance(placement_ids, list):
        raise ValueError("placement_ids must be a list")
    if not placement_ids:
        first_enabled = next((slot for slot in slot_map.values() if slot.get("enabled", True)), None)
        if first_enabled:
            placement_ids = [first_enabled["id"]]
    placements = []
    for placement_id in placement_ids:
        slot = slot_map.get(str(placement_id))
        if not slot:
            raise ValueError(f"unknown placement id: {placement_id}")
        if not slot.get("enabled", True):
            raise ValueError(f"placement is disabled: {placement_id}")
        placements.append(slot)
    if not placements:
        raise ValueError("select at least one enabled placement")

    result = dict(body)
    result["request_id"] = body.get("request_id")
    result["type"] = "image_config"
    result["generation_mode"] = "explore"
    result["placement_ids"] = [slot["id"] for slot in placements]
    result["placements"] = placements
    result["categories"] = sorted({slot["category"] for slot in placements if slot.get("category")})
    result["channels"] = sorted({slot["channel"] for slot in placements if slot.get("channel")})
    first = placements[0]
    result["slot_id"] = first["id"]
    result["platform"] = first["platform"]
    result["placement"] = first["placement"]
    result["channel"] = first["channel"]
    result["category"] = first["category"]
    result["image_form"] = first["image_form"]
    result["ratio"] = first["target_ratio"]
    result["target_width"] = first["target_width"]
    result["target_height"] = first["target_height"]
    result["target_size"] = first["target_size"]
    result["render_width"] = first["render_width"]
    result["render_height"] = first["render_height"]
    result["render_size"] = first["render_size"]
    result["target_kb"] = first["max_file_size_kb"] or 200
    result["sets"] = max(1, min(50, int(body.get("sets") or 1)))
    result["ip_random"] = bool(body.get("ip_random") or body.get("ip") == "随机")
    result["font_reference_randomized"] = bool(body.get("font_reference_enabled", body.get("fontEnabled", True)))
    screen_ui_required = bool(
        body.get("screen_ui_reference_required")
        or body.get("screenUiReferenceRequired")
        or body.get("ui_reference_required")
        or body.get("uiReferenceRequired")
    )
    result["screen_ui_reference_required"] = screen_ui_required
    result["ui_reference_required"] = screen_ui_required
    if result["ui_reference_required"]:
        result["ui_reference"] = "codex_upload_required"
        result["ui_reference_trigger"] = "recognizable_onion_app_screen"
        result["ui_reference_upload_status"] = body.get("ui_reference_upload_status") or "awaiting_codex_upload"
        result["ui_reference_next_action"] = "保存配置后先提醒用户在 Codex 对话上传截图，建议上传洋葱 APP 界面/功能截图；如果没有截图，只能改成弱化/模糊屏幕内容后继续。收到截图前不能进入 prompt、validate-only 或 render。"
    else:
        result["ui_reference"] = "none"
        result["ui_reference_trigger"] = "none"
        result["ui_reference_upload_status"] = "not_required"
        result["ui_reference_next_action"] = ""
    return result


def build_config_html(payload: dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False)
    request_id = html_escape(payload["request_id"])
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>洋葱投放图片配置 - __REQUEST_ID__</title>
  <style>
    :root {
      --ink: #1e2329;
      --body: #3f454d;
      --muted: #7d8791;
      --line: #dfe3e8;
      --soft: #f6f7f9;
      --panel: #ffffff;
      --accent: #e8835a;
      --accent-soft: #fff3ed;
      --ok: #2f7d32;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif;
      background: var(--soft);
      color: var(--body);
      font-size: 14px;
    }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 5;
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 14px 22px;
      background: var(--panel);
      border-bottom: 1px solid var(--line);
    }
    h1 { margin: 0; font-size: 18px; color: var(--ink); }
    .request { color: var(--muted); font-size: 12px; }
    main {
      width: min(1280px, calc(100vw - 32px));
      margin: 16px auto 96px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 380px;
      gap: 16px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .panel h2 { margin: 0 0 12px; font-size: 15px; color: var(--ink); }
    .tabs {
      display: flex;
      gap: 8px;
      margin-bottom: 14px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 10px;
    }
    .tab {
      border: 1px solid var(--line);
      background: white;
      border-radius: 6px;
      padding: 8px 14px;
      cursor: pointer;
      color: var(--ink);
      font: inherit;
    }
    .tab.active {
      border-color: var(--accent);
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 600;
    }
    .slot-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 10px;
    }
    .option {
      text-align: left;
      border: 1px solid var(--line);
      background: white;
      border-radius: 8px;
      padding: 12px;
      cursor: pointer;
      min-height: 96px;
    }
    .option:hover { border-color: var(--accent); }
    .option.active { border-color: var(--accent); background: var(--accent-soft); }
    .option.disabled { opacity: 0.48; cursor: not-allowed; background: #f1f3f5; }
    .option.disabled:hover { border-color: var(--line); }
    .option strong { display: block; color: var(--ink); margin-bottom: 4px; }
    .option span { display: block; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .badges { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 6px; }
    .badge { border: 1px solid var(--line); border-radius: 999px; padding: 2px 7px; color: var(--muted); font-size: 11px; }
    label { display: block; margin: 0 0 6px; color: var(--ink); font-size: 13px; }
    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      background: white;
      color: var(--body);
    }
    textarea { min-height: 86px; resize: vertical; }
    .field { margin-bottom: 16px; }
    .hint { color: var(--muted); font-size: 12px; margin-top: 5px; line-height: 1.5; }
    .thumb-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }
    .thumb-card {
      border: 1px solid var(--line);
      background: white;
      border-radius: 8px;
      min-height: 112px;
      padding: 8px;
      cursor: pointer;
      display: grid;
      grid-template-rows: 64px auto;
      gap: 6px;
      align-items: center;
      text-align: center;
      color: var(--body);
      font: inherit;
    }
    .thumb-card.active { border-color: var(--accent); background: var(--accent-soft); }
    .thumb-card img {
      max-width: 100%;
      max-height: 64px;
      object-fit: contain;
      margin: 0 auto;
      display: block;
    }
    .thumb-card .empty {
      height: 64px;
      display: grid;
      place-items: center;
      border: 1px dashed var(--line);
      border-radius: 6px;
      color: var(--muted);
      font-size: 12px;
    }
    .thumb-card span {
      font-size: 12px;
      line-height: 1.25;
      word-break: break-word;
    }
    .switch-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: white;
    }
    .switch-row input { width: auto; }
    .summary-list {
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }
    .summary-list div {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 8px;
    }
    .summary-list dt { color: var(--muted); }
    .summary-list dd { margin: 0; color: var(--ink); text-align: right; }
    .actions {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      padding: 12px 22px;
      background: rgba(255,255,255,0.96);
      border-top: 1px solid var(--line);
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
    button.primary {
      border: 1px solid var(--accent);
      background: var(--accent);
      color: white;
      border-radius: 6px;
      padding: 10px 18px;
      font: inherit;
      cursor: pointer;
    }
    button.secondary {
      border: 1px solid var(--line);
      background: white;
      color: var(--ink);
      border-radius: 6px;
      padding: 10px 18px;
      font: inherit;
      cursor: pointer;
    }
    .status { margin-right: auto; color: var(--muted); align-self: center; }
    .hidden { display: none; }
  </style>
</head>
<body>
  <div class="topbar">
    <h1>图片生成配置</h1>
    <span class="request">Request __REQUEST_ID__</span>
  </div>
  <main>
    <section class="panel">
      <h2>投放场景</h2>
      <div id="category-tabs" class="tabs"></div>
      <h2>具体版位</h2>
      <div class="hint">可多选。用户只选版位，不选尺寸；卡片内展示目标尺寸、gpt 出图尺寸、压缩上限和一期支持状态。</div>
      <div id="slot-grid" class="slot-grid"></div>
    </section>
    <aside class="panel">
      <h2>配置</h2>
      <div class="field">
        <label for="sets">套数</label>
        <input id="sets" type="number" min="1" max="50" step="1">
        <div class="hint">手动输入，最多 50 套；大批量会分批生成和刷新。</div>
      </div>
      <div class="field">
        <label>Logo</label>
        <div id="logo-grid" class="thumb-grid"></div>
      </div>
      <div class="field">
        <label>IP</label>
        <div id="ip-grid" class="thumb-grid"></div>
        <div class="hint">选择“随机 IP”时，每个版位/每套图都由 Agent 从本地 IP 资产中重新抽取，不锁定同一个角色。</div>
      </div>
      <div class="field">
        <label for="font">字体参考</label>
        <label class="switch-row">
          <span>启用洋葱专属字体参考</span>
          <input id="fontEnabled" type="checkbox" checked>
        </label>
        <div class="hint">启用后生成时从字体参考库完全随机抽取，不需要人工选择具体哪张。</div>
      </div>
      <div id="ctaField" class="field hidden">
        <label for="cta">CTA</label>
        <input id="cta" placeholder="仅信息流填写，例如：立即体验 / 现在下载">
      </div>
      <div class="field">
        <label>界面 / 功能参考图</label>
        <label class="switch-row">
          <span>画面需要展示洋葱 APP 界面/功能截图</span>
          <input id="uiReferenceRequired" type="checkbox">
        </label>
        <div class="hint">只有最终画面里有手机、学习机或其它电子屏幕，并且屏幕要显示可识别的洋葱 APP 功能界面时才勾选。不要在 HTML 里上传；保存后请回到 Codex 上传截图。若不展示具体 UI，可不勾选并让 Agent 弱化/模糊屏幕内容。</div>
      </div>
      <div class="field">
        <label for="notes">补充说明</label>
        <textarea id="notes" placeholder="填写生图建议，例如：更像应用商店截图、不要太信息流、文字更少、人物更靠右。"></textarea>
      </div>
      <h2>摘要</h2>
      <dl id="summary" class="summary-list"></dl>
    </aside>
  </main>
  <div class="actions">
    <span id="status" class="status"></span>
    <button class="secondary" onclick="copyResult()">复制 JSON</button>
    <button class="primary" onclick="submitConfig()">保存配置</button>
  </div>
  <script>
    const DATA = __DATA_JSON__;
    const state = {
      category: DATA.categories?.[0] || DATA.slots[0]?.channel || "应用商店",
      selectedSlotIds: [],
      sets: 2,
      logoIndex: Math.min(1, Math.max(DATA.logoOptions.length - 1, 0)),
      ipIndex: 0,
      fontEnabled: true,
      uiReferenceRequired: false,
      cta: "",
      notes: ""
    };

    function slotsForCategory() { return DATA.slots.filter(slot => slot.channel === state.category || slot.category === state.category); }
    function enabledSlots() { return DATA.slots.filter(slot => slot.enabled !== false); }
    function selectedSlots() {
      const byId = Object.fromEntries(DATA.slots.map(slot => [slot.id, slot]));
      state.selectedSlotIds = state.selectedSlotIds.filter(id => byId[id]?.enabled !== false);
      if (!state.selectedSlotIds.length) {
        const first = slotsForCategory().find(slot => slot.enabled !== false) || enabledSlots()[0];
        if (first) state.selectedSlotIds = [first.id];
      }
      return state.selectedSlotIds.map(id => byId[id]).filter(Boolean);
    }
    function selectedLogo() { return DATA.logoOptions[Number(state.logoIndex)] || DATA.logoOptions[0]; }
    function selectedIp() { return DATA.ipOptions[Number(state.ipIndex)] || DATA.ipOptions[0]; }

    function renderCategories() {
      const tabs = document.getElementById("category-tabs");
      tabs.innerHTML = DATA.categories.map(category => `
        <button class="tab ${category === state.category ? "active" : ""}" onclick="selectCategory('${category}')">${category}</button>
      `).join("");
    }

    function renderSlots() {
      const grid = document.getElementById("slot-grid");
      const slots = slotsForCategory();
      selectedSlots();
      grid.innerHTML = slots.map(slot => `
        <button class="option ${state.selectedSlotIds.includes(slot.id) ? "active" : ""} ${slot.enabled === false ? "disabled" : ""}" onclick="toggleSlot('${slot.id}')" ${slot.enabled === false ? "disabled" : ""}>
          <strong>${slot.platform} · ${slot.name}</strong>
          <span>${slot.sub_channel || ""}</span>
          <span>目标 ${slot.target_size || "-"} / gpt ${slot.render_size || "-"} / &lt;${slot.maxFileSizeKb || "-"}KB</span>
          <span>${slot.imageForm} / ${slot.directness_label || slot.directness || ""}</span>
          ${slot.disabled_reason ? `<span>暂不可选：${slot.disabled_reason}</span>` : ""}
          <div class="badges">
            <span class="badge">target_size</span>
            <span class="badge">render_size</span>
            <span class="badge">disabled_reason</span>
          </div>
        </button>
      `).join("");
    }

    function renderThumbGrid(id, values, selectedIndex, selectFn) {
      document.getElementById(id).innerHTML = values.map((item, index) => `
        <button class="thumb-card ${index === Number(selectedIndex) ? "active" : ""}" onclick="${selectFn}(${index})">
          ${item.thumb ? `<img src="${item.thumb}" alt="">` : `<div class="empty">不用</div>`}
          <span>${item.label || item.value || "未命名"}</span>
        </button>
      `).join("");
    }

    function renderControls() {
      renderThumbGrid("logo-grid", DATA.logoOptions, state.logoIndex, "selectLogo");
      renderThumbGrid("ip-grid", DATA.ipOptions, state.ipIndex, "selectIp");
      document.getElementById("sets").value = state.sets;
      document.getElementById("fontEnabled").checked = state.fontEnabled;
      document.getElementById("uiReferenceRequired").checked = state.uiReferenceRequired;
      document.getElementById("cta").value = state.cta;
      document.getElementById("notes").value = state.notes;
      const allowsCta = selectedSlots().some(slot => slot.cta_policy === "optional" || slot.cta_policy === "required");
      document.getElementById("ctaField").classList.toggle("hidden", !allowsCta);
    }

    function renderSummary() {
      const slots = selectedSlots();
      const logo = selectedLogo();
      const ip = selectedIp();
      const items = [
        ["场景", state.category],
        ["版位", slots.map(slot => `${slot.platform} · ${slot.name}`).join("；")],
        ["尺寸", slots.map(slot => `${slot.target_size} ← gpt ${slot.render_size}`).join("；")],
        ["压缩", slots.map(slot => slot.maxFileSizeKb ? `<${slot.maxFileSizeKb}KB` : "默认 200KB").join("；")],
        ["Logo", logo.label],
        ["IP", ip.random ? "随机：每张重新抽取" : ip.label],
        ["字体参考", state.fontEnabled ? "启用：每张随机抽取" : "不启用"],
        ["屏幕界面", state.uiReferenceRequired ? "需要：保存后回到 Codex 上传截图" : "不展示可识别 UI"],
        ["套数", `${state.sets} 套`],
      ];
      document.getElementById("summary").innerHTML = items.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
    }

    function clampSets(value) {
      const parsed = Number.parseInt(value, 10);
      if (!Number.isFinite(parsed)) return 1;
      return Math.min(50, Math.max(1, parsed));
    }

    function selectCategory(category) {
      state.category = category;
      renderAll();
    }

    function toggleSlot(id) {
      const slot = DATA.slots.find(item => item.id === id);
      if (!slot || slot.enabled === false) return;
      if (state.selectedSlotIds.includes(id)) {
        state.selectedSlotIds = state.selectedSlotIds.filter(item => item !== id);
      } else {
        state.selectedSlotIds.push(id);
      }
      renderAll();
    }
    function selectLogo(index) { state.logoIndex = index; renderAll(); }
    function selectIp(index) { state.ipIndex = index; renderAll(); }

    function collectResult() {
      syncState();
      const slots = selectedSlots();
      const slot = slots[0];
      const logo = selectedLogo();
      const ip = selectedIp();
      const selectedCategories = [...new Set(slots.map(slot => slot.category || slot.channel).filter(Boolean))];
      const selectedChannels = [...new Set(slots.map(slot => slot.channel || slot.category).filter(Boolean))];
      const allowsCta = slots.some(slot => slot.cta_policy === "optional" || slot.cta_policy === "required");
      return {
        request_id: DATA.request_id,
        type: "image_config",
        generation_mode: "explore",
        placement_ids: slots.map(slot => slot.id),
        placements: slots,
        category: selectedCategories[0] || state.category,
        categories: selectedCategories,
        channels: selectedChannels,
        slot_id: slot.id,
        platform: slot.platform,
        placement: slot.name,
        channel: slot.channel,
        image_form: slot.imageForm,
        ratio: slot.target_ratio || slot.ratio,
        target_width: slot.target_width,
        target_height: slot.target_height,
        target_size: slot.target_size,
        render_width: slot.render_width,
        render_height: slot.render_height,
        render_size: slot.render_size,
        target_kb: slot.maxFileSizeKb || 200,
        sets: Number(state.sets),
        logo: logo.value,
        logo_asset_id: logo.asset_id,
        logo_reference_path: logo.path,
        ip: ip.value,
        ip_random: Boolean(ip.random),
        ip_asset_id: ip.asset_id,
        ip_reference_path: ip.path,
        font_reference_enabled: state.fontEnabled,
        font_reference_randomized: state.fontEnabled,
        font_prompt_rule: state.fontEnabled ? "每张图从洋葱专属字体参考中随机抽取；学习字体气质、描边和排版节奏，与当前画面融合；不要求完全一致，不复制参考图里的示例文字。" : "不启用字体参考图。",
        cta: allowsCta ? state.cta.trim() : "",
        screen_ui_reference_required: state.uiReferenceRequired,
        ui_reference_required: state.uiReferenceRequired,
        ui_reference: state.uiReferenceRequired ? "codex_upload_required" : "none",
        ui_reference_trigger: state.uiReferenceRequired ? "recognizable_onion_app_screen" : "none",
        ui_reference_upload_status: state.uiReferenceRequired ? "awaiting_codex_upload" : "not_required",
        ui_reference_note: state.uiReferenceRequired
          ? "只有画面包含可识别的手机/学习机/电子屏幕，并需要展示洋葱 APP 功能界面时才需要截图；不要在 HTML 中上传。保存配置后请回到 Codex 对话上传洋葱 APP 应用内截图。Agent 收到截图后才可进入生图流程。"
          : "本次不展示可识别的洋葱 APP 屏幕 UI；如画面有设备屏幕，应弱化/模糊屏幕内容，不生成具体界面。",
        ui_reference_next_action: state.uiReferenceRequired ? "请用户在 Codex 对话上传截图；收到截图前不能进入 prompt、validate-only 或 render。若用户不上传截图，只能改成弱化/模糊屏幕内容。" : "",
        notes: state.notes.trim()
      };
    }

    function syncState() {
      state.sets = clampSets(document.getElementById("sets").value);
      document.getElementById("sets").value = state.sets;
      state.fontEnabled = document.getElementById("fontEnabled").checked;
      state.uiReferenceRequired = document.getElementById("uiReferenceRequired").checked;
      if (!state.fontEnabled) state.fontRandomIndex = null;
      state.cta = document.getElementById("cta").value;
      state.notes = document.getElementById("notes").value;
      renderSummary();
    }

    async function submitConfig() {
      const response = await fetch("/api/image-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectResult())
      });
      const payload = await response.json();
      document.getElementById("status").textContent = payload.ok ? `已保存：${payload.path}` : `保存失败：${payload.error}`;
    }

    async function copyResult() {
      await navigator.clipboard.writeText(JSON.stringify(collectResult(), null, 2));
      document.getElementById("status").textContent = "配置 JSON 已复制";
    }

    function renderAll() {
      renderCategories();
      renderSlots();
      renderControls();
      renderSummary();
      ["sets", "fontEnabled", "uiReferenceRequired", "cta", "notes"].forEach(id => {
        document.getElementById(id).oninput = syncState;
        document.getElementById(id).onchange = syncState;
      });
    }
    renderAll();
  </script>
</body>
</html>"""
    return template.replace("__REQUEST_ID__", request_id).replace("__DATA_JSON__", data_json)


class OnionInteractionHandler(SimpleHTTPRequestHandler):
    server_version = "OnionInteraction/1.0"

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        clean = posixpath.normpath(parsed.path.lstrip("/"))
        if clean in {"", "."}:
            clean = "image-config"
        if clean == "image-config":
            return str(self.server.output_dir / "__image_config_virtual__.html")  # type: ignore[attr-defined]
        if clean.startswith("skill-assets/"):
            rel = clean.removeprefix("skill-assets/")
            target = (SKILL_DIR / rel).resolve()
            skill_root = SKILL_DIR.resolve()
            if target == skill_root or skill_root in target.parents:
                return str(target)
            return str(self.server.output_dir / "__forbidden__")  # type: ignore[attr-defined]
        return str((self.server.output_dir / clean).resolve())  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/image-sets":
            response = image_sets_payload(self.server.output_dir, self.server.request_id)  # type: ignore[attr-defined]
            self.send_json(response)
            return
        if parsed.path in {"/", "/image-config"}:
            qs = parse_qs(parsed.query)
            request_id = qs.get("request_id", [self.server.request_id])[0]  # type: ignore[attr-defined]
            html = build_config_html(self.server.payload_for(request_id))  # type: ignore[attr-defined]
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def send_json(self, response: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        output_names = {
            "/api/image-config": "image-config-result.json",
            "/api/image-selection": "image-selection-result.json",
        }
        if parsed.path not in output_names and parsed.path != "/api/image-sets":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if parsed.path == "/api/image-sets":
                result = update_image_sets(self.server.output_dir, self.server.request_id, data)  # type: ignore[attr-defined]
                output_path = self.server.output_dir / IMAGE_SETS_FILE  # type: ignore[attr-defined]
                response = {"ok": True, "path": str(output_path), "result": result}
            else:
                output_path = self.server.output_dir / output_names[parsed.path]  # type: ignore[attr-defined]
                if parsed.path == "/api/image-config":
                    data = normalize_config_result(data, slots_by_id(self.server.platform_rules))  # type: ignore[attr-defined]
                atomic_write_json(output_path, data)
                response = {"ok": True, "path": str(output_path), "result": data}
            self.send_json(response)
            return
        except Exception as exc:
            response = {"ok": False, "error": str(exc)}
            self.send_json(response, 400)

    def log_message(self, format: str, *args: Any) -> None:
        print(format % args, file=sys.stderr)


class OnionInteractionServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        output_dir: Path,
        request_id: str,
        context: dict[str, Any] | None,
        platform_rules: Path | None,
    ) -> None:
        super().__init__(server_address, OnionInteractionHandler)
        self.output_dir = output_dir.resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.request_id = request_id
        self.context = context or {}
        self.platform_rules = platform_rules

    def payload_for(self, request_id: str) -> dict[str, Any]:
        return build_config_payload(
            request_id=request_id,
            context=self.context,
            platform_rules=self.platform_rules,
        )


def parse_context(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    path = Path(value)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local Onion image interaction server.")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--context", help="JSON string or JSON file path with upstream copy/direction context")
    parser.add_argument("--platform-rules", help="placement rules JSON path; defaults to plugin config/channel-placement-rules.json")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir).expanduser()
    port = find_free_port(args.port)
    platform_rules = Path(args.platform_rules).expanduser() if args.platform_rules else DEFAULT_CHANNEL_RULES
    if not platform_rules.exists():
        platform_rules = None
    server = OnionInteractionServer(
        ("127.0.0.1", port),
        output_dir=output_dir,
        request_id=args.request_id,
        context=parse_context(args.context),
        platform_rules=platform_rules,
    )
    url = f"http://127.0.0.1:{port}/image-config?request_id={args.request_id}"
    result_path = output_dir / "image-config-result.json"
    print(json.dumps({"ok": True, "url": url, "result_path": str(result_path)}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
