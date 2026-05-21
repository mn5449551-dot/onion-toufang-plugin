from pathlib import Path
import importlib.util
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ENSURE_SCHEMA_SCRIPT = PLUGIN_ROOT / "skills" / "onion-help" / "scripts" / "ensure_base_schema.py"


def load_ensure_schema_module():
    spec = importlib.util.spec_from_file_location("ensure_base_schema", ENSURE_SCHEMA_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BaseSchemaTests(unittest.TestCase):
    def test_feedback_schema_uses_new_feedback_types_and_context_fields(self):
        schema = (PLUGIN_ROOT / "shared" / "base_schema.md").read_text(encoding="utf-8")

        self.assertIn("## 表 3：`image_groups`（图组 / 一行 = 一套图，27 字段）", schema)
        self.assertIn("## 表 4：`feedbacks`（反馈收集池，18 字段）", schema)
        self.assertIn("固定规则反馈 / 主观感受反馈", schema)
        self.assertNotIn("固定规则 / 主观评价", schema)
        self.assertIn("| `关联文案` | link → copies | ❌ |", schema)
        for field in ("请求ID", "方案ID"):
            self.assertIn(f"| `{field}` | text | ❌ |", schema)
        for field in ("请求ID", "方案ID", "问题图位", "渠道", "版位", "图片形式"):
            self.assertIn(f"| `{field}` |", schema)

    def test_base_schema_ensure_script_documents_live_schema_changes(self):
        script = ENSURE_SCHEMA_SCRIPT
        self.assertTrue(script.exists())
        text = script.read_text(encoding="utf-8")

        self.assertIn('"请求ID"', text)
        self.assertIn('"方案ID"', text)
        self.assertIn('"关联文案"', text)
        self.assertIn("view-set-visible-fields", text)

    def test_base_schema_ensure_script_redacts_tokens_from_output(self):
        module = load_ensure_schema_module()
        payload = {
            "base_token": "secret-token",
            "command": ["lark-cli", "--base-token", "secret-token", "--table-id", "tbl"],
            "nested": {"base_token": "secret-token", "command": ["--base-token", "secret-token"]},
        }

        redacted = module.redact_sensitive(payload)
        serialized = str(redacted)

        self.assertNotIn("secret-token", serialized)
        self.assertEqual(redacted["base_token"], "***REDACTED***")
        self.assertEqual(redacted["command"][2], "***REDACTED***")


if __name__ == "__main__":
    unittest.main()
