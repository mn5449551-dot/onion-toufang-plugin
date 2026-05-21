import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_SCRIPT = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "write_selection_feedback.py"
WORKFLOW_SCRIPT = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "image_workflow.py"


def load_feedback_module():
    spec = importlib.util.spec_from_file_location("write_selection_feedback", FEEDBACK_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SelectionFeedbackTests(unittest.TestCase):
    def test_rejected_schemes_become_feedback_records(self):
        module = load_feedback_module()
        selection = {
            "request_id": "req-feedback",
            "rejected_schemes": [
                {
                    "set_id": "set2",
                        "meta": {"渠道": "信息流", "版位": "OPPO 信息流", "图片形式": "单图"},
                        "source": {"copyId": "C-003", "copyRecordId": "recCopy003"},
                        "annotation": {
                        "fixed_rule_feedback": "信息流不能出现学习机外壳。",
                        "subjective_feedback": "整体太像硬广，氛围不够自然。",
                        "problem_positions": ["图1", "图2"],
                        "skip_feedback": False,
                    },
                }
            ],
        }

        records = module.feedback_records_from_selection(selection)

        self.assertEqual(len(records), 2)
        fixed, subjective = records
        self.assertEqual(fixed["fields"]["反馈对象类型"], "图组")
        self.assertEqual(fixed["fields"]["被反馈对象ID"], "req-feedback/set2")
        self.assertEqual(fixed["fields"]["关联文案"], ["recCopy003"])
        self.assertEqual(fixed["fields"]["反馈类型"], "固定规则反馈")
        self.assertEqual(fixed["fields"]["反馈内容"], "信息流不能出现学习机外壳。")
        self.assertEqual(fixed["fields"]["请求ID"], "req-feedback")
        self.assertEqual(fixed["fields"]["方案ID"], "set2")
        self.assertEqual(fixed["fields"]["渠道"], "信息流")
        self.assertEqual(fixed["fields"]["版位"], "OPPO 信息流")
        self.assertEqual(fixed["fields"]["图片形式"], "单图")
        self.assertEqual(fixed["fields"]["问题图位"], "图1、图2")
        self.assertIn("问题图位：图1、图2", fixed["fields"]["建议改法"])
        self.assertIn("渠道：信息流", fixed["fields"]["建议改法"])
        self.assertEqual(fixed["fields"]["处置状态"], "待审")
        self.assertEqual(subjective["fields"]["反馈类型"], "主观感受反馈")
        self.assertEqual(subjective["fields"]["反馈内容"], "整体太像硬广，氛围不够自然。")

    def test_skip_rejection_without_text_is_skipped(self):
        module = load_feedback_module()
        selection = {
            "request_id": "req-feedback",
            "rejected_schemes": [
                {
                    "set_id": "set3",
                    "annotation": {
                        "skip_feedback": True,
                        "fixed_rule_feedback": "",
                        "subjective_feedback": "",
                    },
                }
            ],
        }

        self.assertEqual(module.feedback_records_from_selection(selection), [])

    def test_dry_run_outputs_feedback_records_and_result_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selection_path = root / "image-selection-result.json"
            result_path = root / "image-feedback-result.json"
            selection_path.write_text(
                json.dumps(
                    {
                        "request_id": "req-feedback",
                        "rejected_schemes": [
                            {
                                "set_id": "set2",
                                "annotation": {
                                    "subjective_feedback": "人物表情不够可信。",
                                    "skip_feedback": False,
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(FEEDBACK_SCRIPT),
                    "--selection-result",
                    str(selection_path),
                    "--write-result",
                    str(result_path),
                    "--dry-run",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["feedback_count"], 1)
            self.assertEqual(payload["records"][0]["fields"]["反馈类型"], "主观感受反馈")
            persisted = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["feedback_count"], 1)

    def test_invalid_rejection_feedback_blocks_write(self):
        module = load_feedback_module()
        selection = {
            "request_id": "req-feedback",
            "rejected_schemes": [
                {
                    "set_id": "set2",
                    "annotation": {
                        "skip_feedback": False,
                        "fixed_rule_feedback": "",
                        "subjective_feedback": "",
                    },
                }
            ],
        }

        errors = module.selection_feedback_errors(selection)

        self.assertEqual(len(errors), 1)
        self.assertIn("固定规则反馈 / 主观感受反馈 / 跳过反馈", errors[0])

    def test_workflow_requires_feedback_write_when_rejected_feedback_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-feedback",
                        "placements": [
                            {
                                "id": "p1",
                                "enabled": True,
                                "render_size": "1024x1024",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "image-sets.json").write_text(
                json.dumps({"request_id": "req-feedback", "sets": [{"set_id": "set1", "thumb": ["a.png"]}]}),
                encoding="utf-8",
            )
            (root / "image-selection-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-feedback",
                        "accepted_schemes": [{"set_id": "set1", "thumb": ["a.png"]}],
                        "rejected_schemes": [
                            {
                                "set_id": "set2",
                                "annotation": {
                                    "fixed_rule_feedback": "应用商店图不能出现夸张提分承诺。",
                                    "skip_feedback": False,
                                },
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(WORKFLOW_SCRIPT),
                    "status",
                    "--request-id",
                    "req-feedback",
                    "--output-dir",
                    str(root),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["stage"], "needs_feedback_write")
            self.assertIn("write_selection_feedback.py", payload["next_action"])
            self.assertTrue(payload["artifacts"]["selection_result"])
            self.assertFalse(payload["can_write_base"])

    def test_workflow_blocks_incomplete_rejected_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-feedback",
                        "placements": [{"id": "p1", "enabled": True, "render_size": "1024x1024"}],
                    }
                ),
                encoding="utf-8",
            )
            (root / "image-sets.json").write_text(
                json.dumps({"request_id": "req-feedback", "sets": [{"set_id": "set1", "thumb": ["a.png"]}]}),
                encoding="utf-8",
            )
            (root / "image-selection-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-feedback",
                        "accepted_schemes": [{"set_id": "set1", "thumb": ["a.png"]}],
                        "rejected_schemes": [
                            {
                                "set_id": "set2",
                                "annotation": {"skip_feedback": False, "subjective_feedback": ""},
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(WORKFLOW_SCRIPT),
                    "status",
                    "--request-id",
                    "req-feedback",
                    "--output-dir",
                    str(root),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["stage"], "invalid_selection_feedback")
            self.assertFalse(payload["can_write_base"])


if __name__ == "__main__":
    unittest.main()
