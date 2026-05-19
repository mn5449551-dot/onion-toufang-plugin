#!/usr/bin/env python3
"""Install the onion plugin into Codex Desktop's local plugin marketplace."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PLUGIN_ROOT = SCRIPT_DIR.parent
MARKETPLACE_NAME = "onion-toufang"
PLUGIN_NAME = "onion-toufang"
DISPLAY_NAME = "洋葱投放"
CATEGORY = "Productivity"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def validate_plugin_root(plugin_root: Path) -> None:
    missing = []
    for relative in (".codex-plugin/plugin.json", "skills/onion-image/SKILL.md", "skills/onion-help/SKILL.md"):
        if not (plugin_root / relative).is_file():
            missing.append(relative)
    if missing:
        raise FileNotFoundError(f"not an onion plugin root: {plugin_root}; missing {', '.join(missing)}")


def marketplace_root(codex_home: Path) -> Path:
    return codex_home / "plugins" / "local-marketplaces" / MARKETPLACE_NAME


def marketplace_json() -> dict[str, Any]:
    return {
        "name": MARKETPLACE_NAME,
        "interface": {"displayName": DISPLAY_NAME},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {
                    "source": "local",
                    "path": f"./plugins/{PLUGIN_NAME}",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": CATEGORY,
            }
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def ignore_copy_names(directory: str, names: list[str]) -> set[str]:
    ignored = {
        ".git",
        ".pytest_cache",
        "__pycache__",
        ".DS_Store",
        ".env",
        "node_modules",
    }
    return {name for name in names if name in ignored or name.endswith(".pyc")}


def remove_existing_target(target: Path) -> None:
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)


def copy_plugin(plugin_root: Path, target: Path) -> str:
    remove_existing_target(target)
    shutil.copytree(plugin_root, target, ignore=ignore_copy_names)
    return "copy"


def symlink_plugin(plugin_root: Path, target: Path) -> str:
    remove_existing_target(target)
    target.symlink_to(plugin_root, target_is_directory=True)
    return "symlink"


def install_plugin_source(plugin_root: Path, target: Path, link_mode: str) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if link_mode == "copy":
        return copy_plugin(plugin_root, target)
    if link_mode == "symlink":
        return symlink_plugin(plugin_root, target)

    try:
        return symlink_plugin(plugin_root, target)
    except OSError:
        return copy_plugin(plugin_root, target)


def remove_toml_section(text: str, header: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == header:
            skipping = True
            continue
        if skipping and line.startswith("[") and line.strip().endswith("]"):
            skipping = False
        if not skipping:
            output.append(line)
    return "\n".join(output).rstrip()


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def update_config(codex_home: Path, marketplace_dir: Path) -> Path:
    config_path = codex_home / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    marketplace_header = f"[marketplaces.{MARKETPLACE_NAME}]"
    plugin_header = f'[plugins."{PLUGIN_NAME}@{MARKETPLACE_NAME}"]'

    updated = remove_toml_section(existing, marketplace_header)
    updated = remove_toml_section(updated, plugin_header)
    blocks = [
        marketplace_header,
        f"last_updated = {toml_string(now_iso())}",
        'source_type = "local"',
        f"source = {toml_string(str(marketplace_dir))}",
        "",
        plugin_header,
        "enabled = true",
    ]
    final_text = "\n\n".join(part for part in (updated, "\n".join(blocks)) if part.strip()) + "\n"
    temp = config_path.with_suffix(config_path.suffix + ".tmp")
    temp.write_text(final_text, encoding="utf-8")
    temp.replace(config_path)
    return config_path


def run_setup_wizard(plugin_root: Path) -> dict[str, Any]:
    setup_script = plugin_root / "skills" / "onion-help" / "scripts" / "setup_wizard.py"
    result = subprocess.run(
        [sys.executable, str(setup_script), "ensure"],
        cwd=str(plugin_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload: dict[str, Any] = {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    try:
        payload["report"] = json.loads(result.stdout)
    except json.JSONDecodeError:
        pass
    return payload


def format_setup_failure(setup_result: dict[str, Any]) -> str:
    details = setup_result.get("stderr") or setup_result.get("stdout") or "no output"
    return f"setup_wizard failed with exit code {setup_result.get('returncode')}: {details}"


def install(args: argparse.Namespace) -> dict[str, Any]:
    plugin_root = Path(args.plugin_root).expanduser().resolve()
    codex_home = Path(args.codex_home).expanduser().resolve()
    validate_plugin_root(plugin_root)

    market_root = marketplace_root(codex_home)
    market_file = market_root / ".agents" / "plugins" / "marketplace.json"
    plugin_target = market_root / "plugins" / PLUGIN_NAME

    actual_link_mode = install_plugin_source(plugin_root, plugin_target, args.link_mode)
    write_json(market_file, marketplace_json())
    config_path = update_config(codex_home, market_root)

    setup_result = None
    if not args.skip_setup:
        setup_result = run_setup_wizard(plugin_root)
        if setup_result["returncode"] != 0:
            raise RuntimeError(format_setup_failure(setup_result))

    return {
        "ok": True,
        "operation": "install_codex_plugin",
        "platform": platform.system(),
        "codex_home": str(codex_home),
        "marketplace": MARKETPLACE_NAME,
        "plugin": PLUGIN_NAME,
        "marketplace_dir": str(market_root),
        "marketplace_file": str(market_file),
        "plugin_target": str(plugin_target),
        "config_path": str(config_path),
        "link_mode": actual_link_mode,
        "setup": setup_result,
        "restart_required": True,
        "next_actions": [
            "Restart Codex Desktop or open a new Codex conversation.",
            "If the plugin still does not appear, check ~/.codex/config.toml for onion-toufang entries.",
            "Run onion-help / environment check before the first production write.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install onion-toufang into Codex Desktop.")
    parser.add_argument("--codex-home", default=str(default_codex_home()), help="Codex home directory. Defaults to CODEX_HOME or ~/.codex.")
    parser.add_argument("--plugin-root", default=str(DEFAULT_PLUGIN_ROOT), help="Path to the onion plugin repository root.")
    parser.add_argument("--link-mode", choices=("auto", "symlink", "copy"), default="auto", help="How to place the plugin in the local marketplace.")
    parser.add_argument("--skip-setup", action="store_true", help="Only register the plugin; do not run onion-help setup_wizard.py ensure.")
    args = parser.parse_args(argv)

    try:
        result = install(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
