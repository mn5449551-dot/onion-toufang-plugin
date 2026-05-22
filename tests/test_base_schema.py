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
        self.assertIn('"directions"', text)
        self.assertIn('"洋葱私教班"', text)
        self.assertIn("ensure_direction_function_options", text)
        self.assertIn("view-set-visible-fields", text)

    def test_base_schema_ensure_script_has_private_tutor_function_option(self):
        module = load_ensure_schema_module()
        options = [item["name"] for item in module.DIRECTION_FUNCTION_FIELD["options"]]

        self.assertIn("洋葱私教班", options)
        self.assertIn("AI定制班", options)
        self.assertLess(options.index("AI定制班"), options.index("洋葱私教班"))

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

    def test_direction_function_update_preserves_existing_extra_options(self):
        module = load_ensure_schema_module()
        old_field_list = module.field_list
        old_update = module.update_direction_function
        try:
            module.field_list = lambda _token, _tid: [
                {
                    "name": "功能",
                    "id": "fldFunc",
                    "options": [
                        {"name": "拍题精学", "id": "opt1", "hue": "Blue", "lightness": "Lighter"},
                        {"name": "自定义功能", "id": "optCustom", "hue": "Gray", "lightness": "Lighter"},
                    ],
                }
            ]
            module.update_direction_function = lambda *_args, **_kwargs: {"ok": True}

            result = module.ensure_direction_function_options("token", "tbl", apply=False)
        finally:
            module.field_list = old_field_list
            module.update_direction_function = old_update

        self.assertEqual(result["action"], "update")
        self.assertIn("洋葱私教班", result["missing_options"])
        self.assertIn("自定义功能", result["to"])

    def test_select_option_merge_strips_field_list_metadata(self):
        module = load_ensure_schema_module()

        merged = module.merge_select_options(
            [{"name": "自定义功能", "id": "optCustom", "hue": "Gray", "lightness": "Lighter"}],
            [{"name": "洋葱私教班", "hue": "Yellow", "lightness": "Lighter"}],
        )

        self.assertEqual(merged[0], {"name": "自定义功能", "hue": "Gray", "lightness": "Lighter"})
        self.assertNotIn("id", merged[0])
        self.assertEqual(merged[1]["name"], "洋葱私教班")

    def test_view_order_requires_explicit_view_id(self):
        module = load_ensure_schema_module()
        old_field_list = module.field_list
        old_set_view_order = module.set_view_order
        try:
            module.field_list = lambda *_args, **_kwargs: self.fail("field_list should not be called without view ids")
            module.set_view_order = lambda *_args, **_kwargs: self.fail("set_view_order should not be called without view ids")

            result = module.ensure_view_orders(
                "token",
                {"image_groups": "tblImage", "feedbacks": "tblFeedback"},
                apply=False,
                view_ids={},
            )
        finally:
            module.field_list = old_field_list
            module.set_view_order = old_set_view_order

        self.assertEqual(
            [item["action"] for item in result],
            ["skipped_missing_view_id", "skipped_missing_view_id"],
        )

    def test_view_order_uses_explicit_view_id(self):
        module = load_ensure_schema_module()
        old_field_list = module.field_list
        old_set_view_order = module.set_view_order
        captured = {}
        try:
            module.field_list = lambda _token, _tid: [
                {"name": "图组ID", "id": "fldGroupId"},
                {"name": "状态", "id": "fldStatus"},
                {"name": "图1", "id": "fldImage1"},
            ]

            def fake_set_view_order(_token, table_id, view_id, visible_fields, *, apply):
                captured["table_id"] = table_id
                captured["view_id"] = view_id
                captured["visible_fields"] = visible_fields
                captured["apply"] = apply
                return {"ok": True}

            module.set_view_order = fake_set_view_order

            result = module.ensure_view_orders(
                "token",
                {"image_groups": "tblImage", "feedbacks": "tblFeedback"},
                apply=True,
                view_ids={"image_groups": "viwImage"},
            )
        finally:
            module.field_list = old_field_list
            module.set_view_order = old_set_view_order

        self.assertEqual(result[0]["action"], "set_visible_fields")
        self.assertEqual(captured["table_id"], "tblImage")
        self.assertEqual(captured["view_id"], "viwImage")
        self.assertEqual(captured["visible_fields"][:3], ["fldGroupId", "fldStatus", "fldImage1"])
        self.assertTrue(captured["apply"])
        self.assertEqual(result[1]["action"], "skipped_missing_view_id")


if __name__ == "__main__":
    unittest.main()
