import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Optional


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_SCRIPT = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "image_workflow.py"
VALID_CONFIG = {"request_id": "req-test", "delivery_name": "方向31", "placements": [{"id": "slot1", "render_size": "1280x720"}]}


def run_workflow(output_dir: Path, *extra: str, env: Optional[dict] = None, check: bool = True) -> dict:
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
        env=env,
        check=check,
    )
    output = result.stdout or result.stderr
    return json.loads(output)


class ImageWorkflowTests(unittest.TestCase):
    def test_default_output_dir_uses_runtime_root_env(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env["ONION_AD_OUTPUT_ROOT"] = tmp
            env["HOME"] = home

            result = subprocess.run(
                [
                    sys.executable,
                    str(WORKFLOW_SCRIPT),
                    "status",
                    "--request-id",
                    "req-test",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["stage"], "needs_config")
            self.assertEqual(payload["artifacts"]["output_dir"], str((Path(tmp) / "req-test").resolve()))

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
                        "placements": [{"id": "slot1", "render_size": "1280x720"}],
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
            (root / "image-config-result.json").write_text(json.dumps(VALID_CONFIG), encoding="utf-8")
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
            (root / "image-config-result.json").write_text(json.dumps(VALID_CONFIG), encoding="utf-8")
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

    def test_accepted_selection_without_delivery_name_requires_name_before_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(
                json.dumps({"request_id": "req-test", "placements": [{"id": "slot1", "render_size": "1280x720"}]}),
                encoding="utf-8",
            )
            (root / "image-sets.json").write_text(
                json.dumps({"request_id": "req-test", "sets": [{"set_id": "set1"}]}),
                encoding="utf-8",
            )
            (root / "image-selection-result.json").write_text(
                json.dumps({"request_id": "req-test", "accepted_schemes": [{"set_id": "set1", "thumb": ["set1.png"]}]}),
                encoding="utf-8",
            )

            payload = run_workflow(root)

        self.assertEqual(payload["stage"], "needs_delivery_name")
        self.assertFalse(payload["can_package"])
        self.assertIn("方向名", payload["next_action"])

    def test_packaged_selection_is_ready_for_base_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(json.dumps(VALID_CONFIG), encoding="utf-8")
            (root / "image-sets.json").write_text(
                json.dumps({"request_id": "req-test", "sets": [{"set_id": "set1"}]}),
                encoding="utf-8",
            )
            (root / "image-selection-result.json").write_text(
                json.dumps({"request_id": "req-test", "accepted_schemes": [{"set_id": "set1"}]}),
                encoding="utf-8",
            )
            (root / "方向31.zip").write_bytes(b"zip")

            payload = run_workflow(root)

        self.assertEqual(payload["stage"], "ready_to_write_base")
        self.assertTrue(payload["can_write_base"])
        self.assertTrue(payload["artifacts"]["accepted_package"].endswith("方向31.zip"))
        self.assertIn("write_image_group.py", payload["next_action"])

    def test_write_result_marks_workflow_complete_and_blocks_duplicate_base_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(json.dumps(VALID_CONFIG), encoding="utf-8")
            (root / "image-sets.json").write_text(
                json.dumps({"request_id": "req-test", "sets": [{"set_id": "set1"}]}),
                encoding="utf-8",
            )
            (root / "image-selection-result.json").write_text(
                json.dumps({"request_id": "req-test", "accepted_schemes": [{"set_id": "set1"}]}),
                encoding="utf-8",
            )
            (root / "方向31.zip").write_bytes(b"zip")
            (root / "image-write-result.json").write_text(json.dumps({"ok": True, "record_id": "recImg"}), encoding="utf-8")

            payload = run_workflow(root)

        self.assertEqual(payload["stage"], "complete")
        self.assertFalse(payload["can_write_base"])
        self.assertIn("image-write-result.json", payload["next_action"])

    def test_partial_write_result_requires_attachment_resume_not_duplicate_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(json.dumps(VALID_CONFIG), encoding="utf-8")
            (root / "image-sets.json").write_text(
                json.dumps({"request_id": "req-test", "sets": [{"set_id": "set1"}]}),
                encoding="utf-8",
            )
            (root / "image-selection-result.json").write_text(
                json.dumps({"request_id": "req-test", "accepted_schemes": [{"set_id": "set1"}]}),
                encoding="utf-8",
            )
            (root / "方向31.zip").write_bytes(b"zip")
            (root / "image-write-result.json").write_text(
                json.dumps(
                    {
                        "ok": False,
                        "stage": "attachment_upload_failed",
                        "record_id": "recImg",
                    }
                ),
                encoding="utf-8",
            )

            payload = run_workflow(root)

        self.assertEqual(payload["stage"], "needs_attachment_resume")
        self.assertFalse(payload["can_write_base"])
        self.assertIn("resume", payload["next_action"].lower())

    def test_ready_to_render_requires_non_placeholder_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(json.dumps(VALID_CONFIG), encoding="utf-8")
            env = os.environ.copy()
            env.pop("LAOZHANG_API_KEY", None)
            env["HOME"] = str(root)

            payload = run_workflow(root, env=env)

        self.assertEqual(payload["stage"], "needs_api_key")
        self.assertFalse(payload["can_render"])
        self.assertIn("LAOZHANG_API_KEY", payload["next_action"])

    def test_ready_to_render_points_to_batch_render_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(json.dumps(VALID_CONFIG), encoding="utf-8")
            env = os.environ.copy()
            env["LAOZHANG_API_KEY"] = "test-valid-key"

            payload = run_workflow(root, env=env)

        self.assertEqual(payload["stage"], "ready_to_render")
        self.assertTrue(payload["can_render"])
        self.assertIn("image-render-manifest.json", payload["next_action"])
        self.assertIn("batch_render.py", payload["next_action"])

    def test_request_id_mismatch_blocks_stale_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(json.dumps({"request_id": "other-request"}), encoding="utf-8")

            payload = run_workflow(root)

        self.assertEqual(payload["stage"], "invalid_artifacts")
        self.assertFalse(payload["can_render"])
        self.assertIn("request_id", payload["next_action"])

    def test_missing_placements_blocks_render_even_when_config_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(json.dumps({"request_id": "req-test"}), encoding="utf-8")
            env = os.environ.copy()
            env["LAOZHANG_API_KEY"] = "test-valid-key"

            payload = run_workflow(root, env=env)

        self.assertEqual(payload["stage"], "invalid_config")
        self.assertFalse(payload["can_render"])
        self.assertIn("placements", payload["next_action"])

    def test_ui_reference_uploaded_status_still_requires_reference_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "placements": [{"id": "slot1", "render_size": "1280x720"}],
                        "screen_ui_reference_required": True,
                        "ui_reference_upload_status": "uploaded",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["LAOZHANG_API_KEY"] = "test-valid-key"

            payload = run_workflow(root, env=env)

        self.assertEqual(payload["stage"], "needs_ui_reference_upload")
        self.assertFalse(payload["can_render"])

    def test_iterate_unknown_uploaded_role_blocks_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "image-config-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "generation_mode": "iterate",
                        "iteration_mode": "expand_similar",
                        "uploaded_image_role": "unknown",
                        "placements": [{"id": "slot1", "render_size": "1280x720"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["LAOZHANG_API_KEY"] = "test-valid-key"

            payload = run_workflow(root, env=env)

        self.assertEqual(payload["stage"], "invalid_config")
        self.assertFalse(payload["can_render"])
        self.assertIn("uploaded_image_role", payload["next_action"])


if __name__ == "__main__":
    unittest.main()
