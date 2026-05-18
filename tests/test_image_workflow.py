import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_SCRIPT = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "image_workflow.py"


def run_workflow(output_dir: Path, *extra: str) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            str(WORKFLOW_SCRIPT),
            "status",
            "--request-id",
            "req-test",
            "--output-dir",
            str(output_dir),
            *extra,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return json.loads(result.stdout)


class ImageWorkflowTests(unittest.TestCase):
    def test_missing_config_blocks_paid_rendering(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_workflow(Path(tmp))

        self.assertEqual(payload["stage"], "needs_config")
        self.assertFalse(payload["can_render"])
        self.assertFalse(payload["can_write_base"])
        self.assertIn("interactive_server.py", payload["next_action"])

    def test_ui_reference_requirement_blocks_prompt_and_render_until_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "screen_ui_reference_required": True,
                        "ui_reference_upload_status": "awaiting_codex_upload",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            payload = run_workflow(root)

        self.assertEqual(payload["stage"], "needs_ui_reference_upload")
        self.assertFalse(payload["can_prompt"])
        self.assertFalse(payload["can_render"])
        self.assertIn("上传截图", payload["next_action"])

    def test_rendered_sets_require_selection_before_packaging_or_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(json.dumps({"request_id": "req-test"}), encoding="utf-8")
            (root / "image-sets.json").write_text(
                json.dumps({"request_id": "req-test", "sets": [{"set_id": "set1", "thumb": ["set1.png"]}]}),
                encoding="utf-8",
            )

            payload = run_workflow(root)

        self.assertEqual(payload["stage"], "needs_selection")
        self.assertFalse(payload["can_package"])
        self.assertFalse(payload["can_write_base"])
        self.assertIn("image-selection.html", payload["next_action"])

    def test_accepted_selection_requires_package_before_base_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(json.dumps({"request_id": "req-test"}), encoding="utf-8")
            (root / "image-sets.json").write_text(
                json.dumps({"request_id": "req-test", "sets": [{"set_id": "set1"}]}),
                encoding="utf-8",
            )
            (root / "image-selection-result.json").write_text(
                json.dumps({"request_id": "req-test", "accepted_schemes": [{"set_id": "set1", "thumb": ["set1.png"]}]}),
                encoding="utf-8",
            )

            payload = run_workflow(root)

        self.assertEqual(payload["stage"], "needs_package")
        self.assertTrue(payload["can_package"])
        self.assertFalse(payload["can_write_base"])
        self.assertIn("package_accepted_images.py", payload["next_action"])

    def test_packaged_selection_is_ready_for_base_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(json.dumps({"request_id": "req-test"}), encoding="utf-8")
            (root / "image-sets.json").write_text(
                json.dumps({"request_id": "req-test", "sets": [{"set_id": "set1"}]}),
                encoding="utf-8",
            )
            (root / "image-selection-result.json").write_text(
                json.dumps({"request_id": "req-test", "accepted_schemes": [{"set_id": "set1"}]}),
                encoding="utf-8",
            )
            (root / "req-test-accepted-images.zip").write_bytes(b"zip")

            payload = run_workflow(root)

        self.assertEqual(payload["stage"], "ready_to_write_base")
        self.assertTrue(payload["can_write_base"])
        self.assertIn("write_image_group.py", payload["next_action"])


if __name__ == "__main__":
    unittest.main()
