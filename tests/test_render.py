import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RENDER_PATH = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "render.py"


def load_render_module():
    spec = importlib.util.spec_from_file_location("onion_render", RENDER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.render = load_render_module()

    def test_dotenv_loader_ignores_placeholders_and_existing_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "LAOZHANG_API_KEY=sk-你的企业级令牌",
                        "LAOZHANG_API_BASE=https://example.test/v1",
                        "EXISTING_VALUE=from-file",
                    ]
                ),
                encoding="utf-8",
            )
            old = os.environ.get("EXISTING_VALUE")
            old_key = os.environ.pop("LAOZHANG_API_KEY", None)
            os.environ["EXISTING_VALUE"] = "from-env"
            try:
                self.assertTrue(self.render.load_dotenv_if_exists(env_path))
                self.assertNotIn("LAOZHANG_API_KEY", os.environ)
                self.assertEqual(os.environ["LAOZHANG_API_BASE"], "https://example.test/v1")
                self.assertEqual(os.environ["EXISTING_VALUE"], "from-env")
            finally:
                if old is None:
                    os.environ.pop("EXISTING_VALUE", None)
                else:
                    os.environ["EXISTING_VALUE"] = old
                if old_key is not None:
                    os.environ["LAOZHANG_API_KEY"] = old_key
                os.environ.pop("LAOZHANG_API_BASE", None)

    def test_resolves_plugin_asset_paths(self):
        script_dir = RENDER_PATH.parent
        skill_dir = script_dir.parent
        resolved = self.render.resolve_reference_path(
            "assets/logos/onion-logo-standard-001.png",
            project_root=PLUGIN_ROOT,
            skill_dir=skill_dir,
        )
        self.assertEqual(resolved, skill_dir / "assets" / "logos" / "onion-logo-standard-001.png")
        self.assertTrue(resolved.is_file())

    def test_asset_manifest_standard_paths_exist(self):
        manifest_path = PLUGIN_ROOT / "skills" / "onion-image" / "assets" / "asset-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        asset_ids = [asset["asset_id"] for asset in manifest["assets"]]

        self.assertIn("ip.doubao.junior.standard.001", asset_ids)
        self.assertIn("ip.nina.teacher.fullbody.001", asset_ids)
        self.assertIn("ip.wenxin.teacher.fullbody.001", asset_ids)
        self.assertIn("ip.zhangwuxian.teacher.fullbody.001", asset_ids)
        self.assertIn("logo.onion.standard.001", asset_ids)
        for asset in manifest["assets"]:
            path = PLUGIN_ROOT / "skills" / "onion-image" / asset["path"]
            self.assertTrue(path.is_file(), asset["path"])

    def test_input_json_labeled_references_validate_and_echo_labels(self):
        env = dict(os.environ)
        env.pop("LAOZHANG_API_KEY", None)
        with tempfile.TemporaryDirectory() as tmp:
            input_json = Path(tmp) / "render-input.json"
            input_json.write_text(
                json.dumps(
                    {
                        "prompt": "参考图说明：参考图1 是品牌 Logo；参考图2 是豆包正常版角色。左上角使用参考图1，参考图2站在屏幕旁。",
                        "aspect_ratio": "9:16",
                        "reference_images": [
                            {
                                "label": "参考图1",
                                "role": "品牌 Logo 参考图",
                                "asset_id": "logo.onion.standard.001",
                                "path": "assets/logos/onion-logo-standard-001.png",
                            },
                            {
                                "label": "参考图2",
                                "role": "豆包正常版角色参考图",
                                "asset_id": "ip.doubao.junior.standard.001",
                                "path": "assets/ip-roles/doubao/doubao-junior-standard-001.png",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output = subprocess.run(
                [
                    sys.executable,
                    str(RENDER_PATH),
                    "--input-json",
                    str(input_json),
                    "--output",
                    str(Path(tmp) / "out.png"),
                    "--validate-only",
                ],
                cwd=RENDER_PATH.parent.parent,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        payload = json.loads(output.stdout)
        self.assertEqual(
            [item["label"] for item in payload["reference_image_labels"]],
            ["参考图1", "参考图2"],
        )
        self.assertEqual(payload["reference_image_labels"][1]["asset_id"], "ip.doubao.junior.standard.001")

    def test_labeled_reference_must_be_mentioned_in_prompt(self):
        with self.assertRaisesRegex(ValueError, "prompt must mention"):
            self.render.validate_reference_labels(
                "这里只提到参考图1",
                [
                    {"label": "参考图1", "strict_label": True},
                    {"label": "参考图2", "strict_label": True},
                ],
            )

    def test_save_image_from_response_accepts_data_uri_without_padding(self):
        png_bytes = b"\x89PNG\r\n\x1a\nfake"
        encoded = base64.b64encode(png_bytes).decode("ascii").rstrip("=")
        body = {"data": [{"b64_json": "data:image/png;base64," + encoded}]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.png"
            self.render.save_image_from_response(body, out)
            self.assertEqual(out.read_bytes(), png_bytes)

    def test_cli_validate_only_does_not_require_api_key(self):
        env = dict(os.environ)
        env.pop("LAOZHANG_API_KEY", None)
        output = subprocess.run(
            [
                sys.executable,
                str(RENDER_PATH),
                "--prompt",
                "测试 prompt",
                "--aspect-ratio",
                "3:2",
                "--reference",
                "assets/logos/onion-logo-standard-001.png",
                "--output",
                str(Path(tempfile.gettempdir()) / "onion-render-test.png"),
                "--validate-only",
            ],
            cwd=RENDER_PATH.parent.parent,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        payload = json.loads(output.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["aspect_ratio"], "3:2")
        self.assertEqual(payload["size_label"], "1536x1024")

    def test_cli_validate_only_accepts_explicit_size_and_quality(self):
        env = dict(os.environ)
        env.pop("LAOZHANG_API_KEY", None)
        output = subprocess.run(
            [
                sys.executable,
                str(RENDER_PATH),
                "--prompt",
                "测试 prompt",
                "--size",
                "1568x672",
                "--quality",
                "low",
                "--output",
                str(Path(tempfile.gettempdir()) / "onion-render-size-test.png"),
                "--validate-only",
            ],
            cwd=RENDER_PATH.parent.parent,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        payload = json.loads(output.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["size_label"], "1568x672")
        self.assertEqual(payload["size"], "1568x672")
        self.assertEqual(payload["quality"], "low")
        self.assertEqual(payload["aspect_ratio"], "custom")

    def test_edit_request_omits_unsupported_input_fidelity(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.png"
            ref.write_bytes(b"\x89PNG\r\n\x1a\nfake")
            req = self.render.build_edit_request(
                "https://example.test/v1",
                "sk-test",
                "参考图说明：参考图1 是 Logo。使用参考图1。",
                [ref],
                "1024x1024",
            )
            body = req.data.decode("utf-8", errors="replace")

        self.assertNotIn("input_fidelity", body)


if __name__ == "__main__":
    unittest.main()
