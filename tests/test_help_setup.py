import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SETUP_SCRIPT = PLUGIN_ROOT / "skills" / "onion-help" / "scripts" / "setup_wizard.py"


class HelpSetupWizardTests(unittest.TestCase):
    def run_setup(self, command, home, extra_env=None):
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["ONION_AD_OUTPUT_ROOT"] = str(Path(home) / "runtime")
        env["PATH"] = str(Path(home) / "bin")
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            [sys.executable, str(SETUP_SCRIPT), command],
            cwd=str(PLUGIN_ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result

    def test_bootstrap_creates_env_file_output_root_and_setup_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = self.run_setup("bootstrap", home)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            env_file = home / ".onion-ad" / ".env"
            status_file = home / ".onion-ad" / "setup-status.json"
            usage_file = home / ".onion-ad" / "usage-state.json"
            self.assertTrue(env_file.is_file())
            self.assertTrue((home / "runtime").is_dir())
            self.assertTrue(status_file.is_file())
            self.assertTrue(usage_file.is_file())
            self.assertEqual(payload["operation"], "bootstrap")
            self.assertIn(payload["platform"]["family"], {"mac", "windows", "linux", "other"})
            self.assertTrue(payload["first_use"])
            self.assertEqual(payload["usage_state"]["bootstrap_count"], 1)
            self.assertNotIn("LAOZHANG_API_KEY=", result.stdout)
            self.assertNotIn("sk-你的", result.stdout)

    def test_bootstrap_does_not_overwrite_existing_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            env_dir = home / ".onion-ad"
            env_dir.mkdir(parents=True)
            env_file = env_dir / ".env"
            original = "LAOZHANG_API_KEY=local-secret-value\n"
            env_file.write_text(original, encoding="utf-8")

            result = self.run_setup("bootstrap", home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(env_file.read_text(encoding="utf-8"), original)

    def test_check_reports_missing_lark_cli_without_shelling_to_platform_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = self.run_setup("check", home)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["checks"]["lark_cli"]["status"], "missing")
            self.assertIn("install", " ".join(payload["next_actions"]).lower())
            self.assertNotIn("which lark-cli", result.stdout)
            self.assertNotIn("source ~/.onion-ad/.env", result.stdout)

    def test_ensure_auto_bootstraps_first_use_and_records_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            result = self.run_setup("ensure", home)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            usage_file = home / ".onion-ad" / "usage-state.json"
            self.assertEqual(payload["operation"], "ensure")
            self.assertTrue(payload["auto_bootstrapped"])
            self.assertTrue(payload["first_use"])
            self.assertTrue(usage_file.is_file())
            usage = json.loads(usage_file.read_text(encoding="utf-8"))
            self.assertIn("first_seen_at", usage)
            self.assertIn("last_seen_at", usage)
            self.assertEqual(usage["last_operation"], "ensure")
            self.assertEqual(usage["bootstrap_count"], 1)


if __name__ == "__main__":
    unittest.main()
