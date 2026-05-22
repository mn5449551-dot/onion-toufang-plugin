# Plugin Auto Update Design

**Goal:** Let onion users detect and safely update to the latest GitHub plugin version without spending model/API tokens on every startup.

## Scope

This feature adds a local update checker to the existing `onion-help` setup flow. It does not call paid image APIs, does not modify Feishu/Base data, and does not force-update dirty or non-Git installs.

## Behavior

- `setup_wizard.py ensure` and `setup_wizard.py check` include a `checks.plugin_update` result.
- The update checker stores its latest result in `~/.onion-ad/update-status.json`.
- Normal runs use a 24-hour TTL. If the cache is fresh, the checker returns the cached result and does not contact GitHub.
- Operators can force a check with `setup_wizard.py update-check`.
- Operators can force a safe update with `setup_wizard.py update`.
- `ONION_PLUGIN_AUTO_UPDATE=0` disables automatic network checks and updates.

## Safe Update Rules

The checker may auto-update only when all of these are true:

- the plugin root is inside a Git working tree;
- `git` is available;
- the working tree has no uncommitted changes;
- the current branch has an upstream branch or `origin/main` is available;
- local `HEAD` is an ancestor of the remote target, so `git merge --ff-only` can safely advance.

If any rule fails, the checker returns `status=skipped` or `status=update_available` with a concrete reason and manual next action. It never runs destructive commands and never discards local work.

## Data Contract

`~/.onion-ad/update-status.json` contains:

```json
{
  "schema_version": 1,
  "checked_at": "2026-05-22T17:00:00+08:00",
  "status": "up_to_date|updated|update_available|skipped|disabled|error",
  "auto_update": true,
  "cache_hit": false,
  "current_revision": "abc123",
  "remote_revision": "def456",
  "branch": "main",
  "remote_ref": "origin/main",
  "reason": "",
  "next_action": ""
}
```

## Integration

- Add `shared/scripts/plugin_update.py` for the Git/cache logic.
- Add `update_status_path()` to `shared/scripts/runtime_paths.py`.
- Import the update checker from `setup_wizard.py` and include its result under `checks.plugin_update`.
- Update onion skill gate wording to mention cached update checks and `ONION_PLUGIN_AUTO_UPDATE=0`.
- Update help documentation and tests.

## Acceptance Criteria

- A fresh cache avoids Git/network work.
- `ONION_PLUGIN_AUTO_UPDATE=0` disables the check.
- Dirty worktrees are never updated automatically.
- Clean fast-forwardable worktrees can be updated with `--ff-only`.
- Setup reports include `checks.plugin_update`.
- Full test suite passes.
