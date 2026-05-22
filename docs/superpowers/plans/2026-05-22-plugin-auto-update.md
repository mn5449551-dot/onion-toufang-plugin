# Plugin Auto Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cached, safe plugin update checker to the onion setup/readiness flow.

**Architecture:** Put Git and cache behavior in `shared/scripts/plugin_update.py`, expose the cache path from `runtime_paths.py`, and have `setup_wizard.py` include update status in its normal report. Keep skill docs as the operational contract for agents.

**Tech Stack:** Python standard library, `git` CLI, unittest.

---

### Task 1: Runtime Path and Update Checker

**Files:**
- Modify: `shared/scripts/runtime_paths.py`
- Create: `shared/scripts/plugin_update.py`
- Test: `tests/test_plugin_update.py`

- [ ] **Step 1: Write failing tests**

Create tests for disabled checks, fresh-cache behavior, dirty worktree skip, and fast-forward updates using temporary Git repositories.

- [ ] **Step 2: Verify failures**

Run `python3 -m unittest tests.test_plugin_update`.

- [ ] **Step 3: Implement update checker**

Add `update_status_path()` and implement `check_or_update(force=False, auto_update=True, cache_ttl_hours=24, plugin_root=None)`.

- [ ] **Step 4: Verify tests pass**

Run `python3 -m unittest tests.test_plugin_update`.

### Task 2: Setup Wizard Integration

**Files:**
- Modify: `skills/onion-help/scripts/setup_wizard.py`
- Modify: `tests/test_help_setup.py`

- [ ] **Step 1: Write failing tests**

Assert setup reports include `checks.plugin_update`, honor disabled update checks, and expose `update-check`/`update` commands.

- [ ] **Step 2: Verify failures**

Run `python3 -m unittest tests.test_help_setup`.

- [ ] **Step 3: Implement setup integration**

Import `plugin_update`, include update status in `build_report()`, and add CLI commands.

- [ ] **Step 4: Verify tests pass**

Run `python3 -m unittest tests.test_help_setup`.

### Task 3: Documentation and Skill Contracts

**Files:**
- Modify: `skills/onion-help/SKILL.md`
- Modify: `skills/onion-help/references/环境自检清单.md`
- Modify: `skills/onion-using/SKILL.md`
- Modify: `skills/onion-direction/SKILL.md`
- Modify: `skills/onion-copy/SKILL.md`
- Modify: `skills/onion-image/SKILL.md`
- Modify: `skills/onion-image-iterate/SKILL.md`
- Modify: `tests/test_skill_contracts.py`

- [ ] **Step 1: Write contract assertions**

Assert docs mention cached update checks, `update-status.json`, and `ONION_PLUGIN_AUTO_UPDATE=0`.

- [ ] **Step 2: Update docs**

Document 24-hour cache, safe fast-forward behavior, and disable/force commands.

- [ ] **Step 3: Verify contracts**

Run `python3 -m unittest tests.test_skill_contracts`.

### Task 4: Full Verification and Commit

**Files:**
- All changed files

- [ ] **Step 1: Run focused tests**

Run `python3 -m unittest tests.test_plugin_update tests.test_help_setup tests.test_skill_contracts`.

- [ ] **Step 2: Run full suite**

Run `python3 -m unittest discover -s tests`.

- [ ] **Step 3: Commit**

Commit with `feat: add safe plugin update checks`.
