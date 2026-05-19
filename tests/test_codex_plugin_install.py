import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = PLUGIN_ROOT / "scripts" / "install_codex_plugin.py"


class CodexPluginInstallTests(unittest.TestCase):
    def run_installer(self, codex_home, *args, plugin_root=PLUGIN_ROOT, skip_setup=True):
        env = os.environ.copy()
        env["HOME"] = str(Path(codex_home).parent)
        command = [
            sys.executable,
            str(INSTALL_SCRIPT),
            "--codex-home",
            str(codex_home),
            "--plugin-root",
            str(plugin_root),
            "--link-mode",
            "copy",
            *args,
        ]
        if skip_setup:
            command.append("--skip-setup")
        result = subprocess.run(
            command,
            cwd=str(PLUGIN_ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result

    def make_plugin_root(self, directory, setup_source):
        plugin_root = Path(directory) / "fake-onion-plugin"
        (plugin_root / ".codex-plugin").mkdir(parents=True)
        (plugin_root / "skills" / "onion-image").mkdir(parents=True)
        (plugin_root / "skills" / "onion-help" / "scripts").mkdir(parents=True)
        (plugin_root / ".codex-plugin" / "plugin.json").write_text('{"name":"onion-toufang"}\n', encoding="utf-8")
        (plugin_root / "skills" / "onion-image" / "SKILL.md").write_text("---\nname: onion-image\n---\n", encoding="utf-8")
        (plugin_root / "skills" / "onion-help" / "SKILL.md").write_text("---\nname: onion-help\n---\n", encoding="utf-8")
        (plugin_root / "skills" / "onion-help" / "scripts" / "setup_wizard.py").write_text(setup_source, encoding="utf-8")
        return plugin_root

    def test_installer_registers_local_marketplace_and_plugin_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            result = self.run_installer(codex_home)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            marketplace_file = codex_home / "plugins" / "local-marketplaces" / "onion-toufang" / ".agents" / "plugins" / "marketplace.json"
            config_file = codex_home / "config.toml"
            plugin_copy = codex_home / "plugins" / "local-marketplaces" / "onion-toufang" / "plugins" / "onion-toufang"

            self.assertTrue(marketplace_file.is_file())
            self.assertTrue(config_file.is_file())
            self.assertTrue((plugin_copy / ".codex-plugin" / "plugin.json").is_file())
            self.assertEqual(payload["marketplace"], "onion-toufang")
            self.assertEqual(payload["plugin"], "onion-toufang")
            self.assertEqual(payload["link_mode"], "copy")
            self.assertTrue(payload["restart_required"])

            marketplace = json.loads(marketplace_file.read_text(encoding="utf-8"))
            self.assertEqual(marketplace["name"], "onion-toufang")
            self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/onion-toufang")

            config = config_file.read_text(encoding="utf-8")
            self.assertIn("[marketplaces.onion-toufang]", config)
            self.assertIn('source_type = "local"', config)
            self.assertIn("[plugins.\"onion-toufang@onion-toufang\"]", config)
            self.assertIn("enabled = true", config)

    def test_installer_is_idempotent_and_preserves_unrelated_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir(parents=True)
            config_file = codex_home / "config.toml"
            config_file.write_text(
                "[profiles.default]\nmodel = \"gpt-5.5\"\n\n[plugins.\"github@claude-plugins-official\"]\nenabled = true\n",
                encoding="utf-8",
            )

            first = self.run_installer(codex_home)
            second = self.run_installer(codex_home)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            config = config_file.read_text(encoding="utf-8")
            self.assertIn("[profiles.default]", config)
            self.assertIn("[plugins.\"github@claude-plugins-official\"]", config)
            self.assertEqual(config.count("[marketplaces.onion-toufang]"), 1)
            self.assertEqual(config.count("[plugins.\"onion-toufang@onion-toufang\"]"), 1)

    def test_default_install_runs_setup_wizard(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root = self.make_plugin_root(
                tmp,
                "import json\n"
                "print(json.dumps({'ok': True, 'operation': 'ensure'}))\n",
            )
            codex_home = Path(tmp) / ".codex"

            result = self.run_installer(codex_home, plugin_root=plugin_root, skip_setup=False)

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["setup"]["returncode"], 0)
            self.assertEqual(payload["setup"]["report"]["operation"], "ensure")

    def test_default_install_fails_when_setup_wizard_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_root = self.make_plugin_root(
                tmp,
                "import sys\n"
                "print('setup failed intentionally', file=sys.stderr)\n"
                "sys.exit(5)\n",
            )
            codex_home = Path(tmp) / ".codex"

            result = self.run_installer(codex_home, plugin_root=plugin_root, skip_setup=False)

            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stderr)
            self.assertFalse(payload["ok"])
            self.assertIn("setup_wizard failed", payload["error"])
            self.assertIn("setup failed intentionally", payload["error"])

    def test_readme_has_codex_desktop_install_entrypoint(self):
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("scripts/install_codex_plugin.py", readme)
        self.assertIn("重启 Codex Desktop", readme)
        self.assertIn("下载源码", readme)
        self.assertIn("py -3 -m pip install Pillow", readme)


if __name__ == "__main__":
    unittest.main()
