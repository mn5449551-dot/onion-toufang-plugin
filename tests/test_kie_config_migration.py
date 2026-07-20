from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "migrate_kie_config.py"


def load_module():
    spec = importlib.util.spec_from_file_location("migrate_kie_config", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KieConfigMigrationTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_migration_preserves_existing_values_and_backs_up_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.env"
            target = root / "runtime" / ".env"
            source.write_text("KIE_API_KEY=secret-value\nKIE_BASE_URL=https://api.example\n", encoding="utf-8")
            target.parent.mkdir(parents=True)
            target.write_text("ONION_BASE_APP_TOKEN=base-token\nKIE_API_KEY=old-value\n", encoding="utf-8")

            result = self.module.migrate(source, target)
            content = target.read_text(encoding="utf-8")
            backup_exists = Path(str(result["backup"])).is_file()

        self.assertTrue(result["ok"])
        self.assertEqual(result["synced_keys"], list(self.module.SYNC_KEYS))
        self.assertIn("ONION_BASE_APP_TOKEN=base-token", content)
        self.assertIn("KIE_API_KEY=secret-value", content)
        self.assertIn("KIE_BASE_URL=https://api.example", content)
        self.assertIn("KIE_UPLOAD_BASE_URL=https://kieai.redpandaai.co", content)
        self.assertNotIn("secret-value", str(result))
        self.assertTrue(backup_exists)

    def test_missing_key_does_not_create_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.env"
            target = root / "runtime" / ".env"
            source.write_text("KIE_BASE_URL=https://api.example\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing or a placeholder"):
                self.module.migrate(source, target)

            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
