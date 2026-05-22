import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
UPDATE_SCRIPT = PLUGIN_ROOT / "shared" / "scripts" / "plugin_update.py"


def load_update_module():
    spec = importlib.util.spec_from_file_location("plugin_update", UPDATE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PluginUpdateTests(unittest.TestCase):
    def run_git(self, cwd, *args):
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def make_repo(self, root):
        repo = Path(root) / "repo"
        repo.mkdir(parents=True)
        self.run_git(repo, "init", "-b", "main")
        self.run_git(repo, "config", "user.email", "test@example.com")
        self.run_git(repo, "config", "user.name", "Test User")
        (repo / "README.md").write_text("one\n", encoding="utf-8")
        self.run_git(repo, "add", "README.md")
        self.run_git(repo, "commit", "-m", "initial")
        return repo

    def test_disabled_by_env_writes_disabled_status(self):
        module = load_update_module()
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "update-status.json"

            result = module.check_or_update(
                plugin_root=Path(tmp) / "missing",
                state_path=state_path,
                env={"ONION_PLUGIN_AUTO_UPDATE": "0"},
            )

            self.assertEqual(result["status"], "disabled")
            self.assertFalse(result["auto_update"])
            self.assertTrue(state_path.is_file())
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["status"], "disabled")

    def test_fresh_cache_returns_without_git_work(self):
        module = load_update_module()
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "update-status.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "checked_at": module.now_iso(),
                        "status": "up_to_date",
                        "auto_update": True,
                        "cache_hit": False,
                        "current_revision": "abc123",
                        "remote_revision": "abc123",
                        "branch": "main",
                        "remote_ref": "origin/main",
                        "reason": "",
                        "next_action": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = module.check_or_update(
                plugin_root=Path(tmp) / "not-a-repo",
                state_path=state_path,
                cache_ttl_hours=24,
            )

            self.assertEqual(result["status"], "up_to_date")
            self.assertTrue(result["cache_hit"])
            self.assertEqual(result["current_revision"], "abc123")

    def test_dirty_worktree_skips_auto_update(self):
        module = load_update_module()
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.make_repo(tmp)
            (repo / "README.md").write_text("dirty\n", encoding="utf-8")

            result = module.check_or_update(
                plugin_root=repo,
                state_path=Path(tmp) / "update-status.json",
                force=True,
            )

            self.assertEqual(result["status"], "skipped")
            self.assertIn("dirty", result["reason"])
            self.assertIn("commit or stash", result["next_action"])

    def test_clean_fast_forward_worktree_updates(self):
        module = load_update_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            source = self.make_repo(root / "source-root")
            self.run_git(remote.parent, "init", "--bare", str(remote))
            self.run_git(source, "remote", "add", "origin", str(remote))
            self.run_git(source, "push", "-u", "origin", "main")

            clone = root / "clone"
            self.run_git(root, "clone", str(remote), str(clone))
            (source / "README.md").write_text("two\n", encoding="utf-8")
            self.run_git(source, "add", "README.md")
            self.run_git(source, "commit", "-m", "second")
            self.run_git(source, "push")
            expected_head = self.run_git(source, "rev-parse", "HEAD")

            result = module.check_or_update(
                plugin_root=clone,
                state_path=root / "update-status.json",
                force=True,
            )

            self.assertEqual(result["status"], "updated")
            self.assertEqual(self.run_git(clone, "rev-parse", "HEAD"), expected_head)
            self.assertEqual(result["current_revision"], expected_head)
            self.assertEqual(result["remote_revision"], expected_head)

    def test_fetch_failure_reports_error_instead_of_using_stale_remote_ref(self):
        module = load_update_module()
        calls = []

        def runner(command, cwd, text, stdout, stderr):
            calls.append(command)
            args = command[1:]
            if args == ["rev-parse", "--is-inside-work-tree"]:
                return subprocess.CompletedProcess(command, 0, "true\n", "")
            if args == ["branch", "--show-current"]:
                return subprocess.CompletedProcess(command, 0, "main\n", "")
            if args == ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]:
                return subprocess.CompletedProcess(command, 0, "origin/main\n", "")
            if args == ["rev-parse", "HEAD"]:
                return subprocess.CompletedProcess(command, 0, "local\n", "")
            if args == ["status", "--porcelain"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            if args == ["fetch", "--quiet"]:
                return subprocess.CompletedProcess(command, 1, "", "network down")
            if args == ["rev-parse", "origin/main"]:
                return subprocess.CompletedProcess(command, 0, "stale\n", "")
            return subprocess.CompletedProcess(command, 1, "", "unexpected")

        with tempfile.TemporaryDirectory() as tmp:
            result = module.check_or_update(
                plugin_root=Path(tmp),
                state_path=Path(tmp) / "update-status.json",
                force=True,
                runner=runner,
            )

        self.assertEqual(result["status"], "error")
        self.assertIn("network down", result["reason"])
        self.assertNotIn(["git", "merge", "--ff-only", "origin/main"], calls)


if __name__ == "__main__":
    unittest.main()
