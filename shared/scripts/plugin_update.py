from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime_paths import update_status_path


SCHEMA_VERSION = 1
DEFAULT_CACHE_TTL_HOURS = 24


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def result(
    status: str,
    *,
    auto_update: bool,
    cache_hit: bool = False,
    current_revision: str = "",
    remote_revision: str = "",
    branch: str = "",
    remote_ref: str = "",
    reason: str = "",
    next_action: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "checked_at": now_iso(),
        "status": status,
        "auto_update": auto_update,
        "cache_hit": cache_hit,
        "current_revision": current_revision,
        "remote_revision": remote_revision,
        "branch": branch,
        "remote_ref": remote_ref,
        "reason": reason,
        "next_action": next_action,
    }


def is_cache_fresh(cached: dict[str, Any], cache_ttl_hours: int) -> bool:
    checked_at = parse_time(str(cached.get("checked_at") or ""))
    if not checked_at:
        return False
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - checked_at.astimezone(timezone.utc) < timedelta(hours=cache_ttl_hours)


def run_git(
    plugin_root: Path,
    args: Sequence[str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> subprocess.CompletedProcess[str]:
    return runner(
        ["git", *args],
        cwd=str(plugin_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_ok(
    plugin_root: Path,
    args: Sequence[str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[bool, str]:
    completed = run_git(plugin_root, args, runner)
    output = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode == 0, output


def git_stdout(
    plugin_root: Path,
    args: Sequence[str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    ok, output = git_ok(plugin_root, args, runner)
    return output if ok else ""


def resolve_remote_ref(
    plugin_root: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[str, str]:
    branch = git_stdout(plugin_root, ["branch", "--show-current"], runner)
    upstream = git_stdout(plugin_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], runner)
    if upstream:
        return branch, upstream
    for candidate in ("origin/main", "origin/master"):
        ok, _ = git_ok(plugin_root, ["rev-parse", "--verify", candidate], runner)
        if ok:
            return branch, candidate
    return branch, ""


def is_disabled(env: Mapping[str, str]) -> bool:
    return str(env.get("ONION_PLUGIN_AUTO_UPDATE") or "").strip().lower() in {"0", "false", "no", "off"}


def check_or_update(
    *,
    plugin_root: Path | None = None,
    state_path: Path | None = None,
    force: bool = False,
    auto_update: bool = True,
    cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    env: Mapping[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    env = env or os.environ
    plugin_root = Path(plugin_root or Path(__file__).resolve().parents[2]).resolve()
    state_path = Path(state_path or update_status_path())
    auto_update = bool(auto_update) and not is_disabled(env)

    if is_disabled(env):
        payload = result("disabled", auto_update=False, reason="ONION_PLUGIN_AUTO_UPDATE=0")
        write_json(state_path, payload)
        return payload

    cached = read_json(state_path)
    if cached and not force and is_cache_fresh(cached, cache_ttl_hours):
        cached = dict(cached)
        cached["cache_hit"] = True
        return cached

    if not shutil.which("git"):
        payload = result("skipped", auto_update=auto_update, reason="git not found", next_action="Install git, or update the plugin manually.")
        write_json(state_path, payload)
        return payload

    ok, _ = git_ok(plugin_root, ["rev-parse", "--is-inside-work-tree"], runner)
    if not ok:
        payload = result(
            "skipped",
            auto_update=auto_update,
            reason="plugin root is not a git worktree",
            next_action="Use the plugin installer or download the latest GitHub version manually.",
        )
        write_json(state_path, payload)
        return payload

    branch, remote_ref = resolve_remote_ref(plugin_root, runner)
    current = git_stdout(plugin_root, ["rev-parse", "HEAD"], runner)
    dirty = git_stdout(plugin_root, ["status", "--porcelain"], runner)
    if dirty:
        payload = result(
            "skipped",
            auto_update=auto_update,
            current_revision=current,
            branch=branch,
            remote_ref=remote_ref,
            reason="dirty worktree",
            next_action="Please commit or stash local plugin changes before updating.",
        )
        write_json(state_path, payload)
        return payload

    if not remote_ref:
        payload = result(
            "skipped",
            auto_update=auto_update,
            current_revision=current,
            branch=branch,
            reason="no remote tracking branch",
            next_action="Set an upstream branch or update the plugin manually.",
        )
        write_json(state_path, payload)
        return payload

    fetch = run_git(plugin_root, ["fetch", "--quiet"], runner)
    if fetch.returncode != 0:
        payload = result(
            "error",
            auto_update=auto_update,
            current_revision=current,
            branch=branch,
            remote_ref=remote_ref,
            reason=(fetch.stderr or fetch.stdout or "git fetch failed").strip(),
            next_action="Check network access, then run setup_wizard.py update-check again.",
        )
        write_json(state_path, payload)
        return payload
    remote = git_stdout(plugin_root, ["rev-parse", remote_ref], runner)
    if not remote:
        payload = result(
            "skipped",
            auto_update=auto_update,
            current_revision=current,
            branch=branch,
            remote_ref=remote_ref,
            reason="remote revision unavailable",
            next_action="Check network access or update the plugin manually.",
        )
        write_json(state_path, payload)
        return payload
    if current == remote:
        payload = result("up_to_date", auto_update=auto_update, current_revision=current, remote_revision=remote, branch=branch, remote_ref=remote_ref)
        write_json(state_path, payload)
        return payload

    ancestor_ok, _ = git_ok(plugin_root, ["merge-base", "--is-ancestor", "HEAD", remote_ref], runner)
    if not ancestor_ok:
        payload = result(
            "update_available",
            auto_update=auto_update,
            current_revision=current,
            remote_revision=remote,
            branch=branch,
            remote_ref=remote_ref,
            reason="local branch has diverged from remote",
            next_action="Review local commits before updating the plugin.",
        )
        write_json(state_path, payload)
        return payload

    if not auto_update:
        payload = result(
            "update_available",
            auto_update=False,
            current_revision=current,
            remote_revision=remote,
            branch=branch,
            remote_ref=remote_ref,
            reason="auto update disabled for this run",
            next_action="Run setup_wizard.py update to fast-forward the plugin safely.",
        )
        write_json(state_path, payload)
        return payload

    merge = run_git(plugin_root, ["merge", "--ff-only", remote_ref], runner)
    if merge.returncode != 0:
        payload = result(
            "error",
            auto_update=auto_update,
            current_revision=current,
            remote_revision=remote,
            branch=branch,
            remote_ref=remote_ref,
            reason=(merge.stderr or merge.stdout or "git merge --ff-only failed").strip(),
            next_action="Update manually after inspecting the Git error.",
        )
        write_json(state_path, payload)
        return payload

    updated = git_stdout(plugin_root, ["rev-parse", "HEAD"], runner) or remote
    payload = result("updated", auto_update=True, current_revision=updated, remote_revision=remote, branch=branch, remote_ref=remote_ref)
    write_json(state_path, payload)
    return payload


def main() -> int:
    payload = check_or_update(force=True)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") not in {"error"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
