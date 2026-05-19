from pathlib import Path
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class BaseSchemaTests(unittest.TestCase):
    def test_feedback_schema_uses_new_feedback_types_and_context_fields(self):
        schema = (PLUGIN_ROOT / "shared" / "base_schema.md").read_text(encoding="utf-8")

        self.assertIn("## 表 4：`feedbacks`（反馈收集池，17 字段）", schema)
        self.assertIn("固定规则反馈 / 主观感受反馈", schema)
        self.assertNotIn("固定规则 / 主观评价", schema)
        for field in ("请求ID", "方案ID", "问题图位", "渠道", "版位", "图片形式"):
            self.assertIn(f"| `{field}` |", schema)


if __name__ == "__main__":
    unittest.main()
