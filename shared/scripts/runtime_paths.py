from __future__ import annotations

import os
from pathlib import Path
import platform
import tempfile


def default_output_root(system_name: str | None = None) -> Path:
    system = (system_name or platform.system()).lower()
    if system == "windows":
        return (Path(tempfile.gettempdir()) / "onion-ad").resolve()
    return Path("/tmp/onion-ad").resolve()


def output_root() -> Path:
    configured = os.environ.get("ONION_AD_OUTPUT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return default_output_root()


def request_output_dir(request_id: str) -> Path:
    return output_root() / str(request_id)


def user_state_dir() -> Path:
    return Path.home() / ".onion-ad"


def setup_status_path() -> Path:
    return user_state_dir() / "setup-status.json"


def usage_state_path() -> Path:
    return user_state_dir() / "usage-state.json"
