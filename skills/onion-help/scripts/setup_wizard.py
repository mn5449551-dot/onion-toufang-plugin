#!/usr/bin/env python3
"""Cross-platform setup and readiness checks for the onion plugin."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parents[2]
SHARED_SCRIPTS = PLUGIN_ROOT / "shared" / "scripts"
if str(SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS))

from runtime_paths import output_root, setup_status_path  # noqa: E402


ENV_DIR = Path.home() / ".onion-ad"
ENV_FILE = ENV_DIR / ".env"
ENV_TEMPLATE = PLUGIN_ROOT / ".env.template"
PLACEHOLDER_MARKERS = ("你的", "占位", "sk-xxx", "sk-your-key", "your-key")
PLUGIN_VERSION = "1.1.0"


def platform_profile(system_name: str | None = None) -> dict[str, str]:
    name = system_name or platform.system()
    lowered = name.lower()
    if lowered == "darwin":
        family = "mac"
    elif lowered == "windows":
        family = "windows"
    elif lowered == "linux":
        family = "linux"
    else:
        family = "other"
    return {"system": name, "family": family}


def read_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def env_value(key: str, values: dict[str, str]) -> str:
    return str(os.environ.get(key) or values.get(key) or "").strip()


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return not value or any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def check_env(values: dict[str, str]) -> dict[str, Any]:
    if not ENV_FILE.is_file():
        return {"status": "missing", "path": str(ENV_FILE)}
    image_key = env_value("LAOZHANG_API_KEY", values)
    base_token = env_value("ONION_BASE_APP_TOKEN", values)
    missing = []
    if is_placeholder(image_key):
        missing.append("LAOZHANG_API_KEY")
    if not base_token:
        missing.append("ONION_BASE_APP_TOKEN")
    return {
        "status": "ok" if not missing else "incomplete",
        "path": str(ENV_FILE),
        "missing_or_placeholder": missing,
    }


def check_lark_cli() -> dict[str, Any]:
    configured = os.environ.get("LARK_CLI_BIN")
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return {"status": "ok", "path": str(path.resolve())}
        return {"status": "missing", "path": configured}
    found = shutil.which("lark-cli")
    return {"status": "ok", "path": found} if found else {"status": "missing"}


def check_python() -> dict[str, Any]:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return {"status": "ok" if sys.version_info >= (3, 8) else "unsupported", "version": version}


def check_pillow() -> dict[str, Any]:
    try:
        from PIL import Image  # type: ignore

        return {"status": "ok", "version": getattr(Image, "__version__", "unknown")}
    except Exception:
        return {"status": "missing"}


def check_scripts_compile() -> dict[str, Any]:
    scripts = [
        PLUGIN_ROOT / "shared" / "scripts" / "base_ops.py",
        PLUGIN_ROOT / "shared" / "scripts" / "write_record.py",
        PLUGIN_ROOT / "shared" / "scripts" / "update_status.py",
        PLUGIN_ROOT / "shared" / "scripts" / "retry_pending.py",
        PLUGIN_ROOT / "shared" / "scripts" / "write_image_group.py",
        PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "render.py",
        PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "image_workflow.py",
    ]
    missing = [str(path.relative_to(PLUGIN_ROOT)) for path in scripts if not path.is_file()]
    return {"status": "ok" if not missing else "missing", "missing": missing}


def next_actions(checks: dict[str, Any], profile: dict[str, str]) -> list[str]:
    actions = []
    if checks["env_file"]["status"] == "missing":
        actions.append("Run bootstrap to create ~/.onion-ad/.env, then fill LAOZHANG_API_KEY.")
    elif checks["env_file"]["status"] == "incomplete":
        actions.append("Open ~/.onion-ad/.env and fill missing or placeholder keys.")
    if checks["lark_cli"]["status"] == "missing":
        actions.append(f"Install lark-cli for {profile['family']} and run lark-cli auth login.")
    if checks["pillow"]["status"] == "missing":
        actions.append("Install Pillow with python -m pip install Pillow.")
    if checks["python"]["status"] != "ok":
        actions.append("Use Python 3.8 or newer.")
    return actions


def build_report(operation: str) -> dict[str, Any]:
    values = read_env_file()
    profile = platform_profile()
    checks = {
        "env_file": check_env(values),
        "lark_cli": check_lark_cli(),
        "python": check_python(),
        "pillow": check_pillow(),
        "scripts": check_scripts_compile(),
        "output_root": {"status": "ok", "path": str(output_root())},
    }
    actions = next_actions(checks, profile)
    return {
        "ok": True,
        "operation": operation,
        "plugin_version": PLUGIN_VERSION,
        "platform": profile,
        "output_root": str(output_root()),
        "setup_status_path": str(setup_status_path()),
        "ready": not actions and all(item.get("status") == "ok" for item in checks.values()),
        "checks": checks,
        "next_actions": actions,
    }


def bootstrap() -> dict[str, Any]:
    ENV_DIR.mkdir(parents=True, exist_ok=True)
    output_root().mkdir(parents=True, exist_ok=True)
    env_created = False
    if not ENV_FILE.exists():
        if not ENV_TEMPLATE.is_file():
            raise FileNotFoundError(f"missing env template: {ENV_TEMPLATE}")
        shutil.copyfile(ENV_TEMPLATE, ENV_FILE)
        env_created = True
        try:
            ENV_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    report = build_report("bootstrap")
    report["env_created"] = env_created
    write_setup_status(report)
    return report


def write_setup_status(report: dict[str, Any]) -> None:
    path = setup_status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    status = {
        "plugin_version": report["plugin_version"],
        "platform": report["platform"],
        "output_root": report["output_root"],
        "ready": report["ready"],
        "checks": report["checks"],
        "next_actions": report["next_actions"],
    }
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Onion plugin setup and readiness checks.")
    parser.add_argument("command", choices=("check", "bootstrap", "doctor"))
    args = parser.parse_args(argv)

    try:
        if args.command == "bootstrap":
            report = bootstrap()
        else:
            report = build_report(args.command)
            write_setup_status(report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
