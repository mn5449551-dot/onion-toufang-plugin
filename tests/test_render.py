import base64
import hashlib
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

    def test_app_logo_uses_approved_hd_asset_and_keeps_unlisted_compatibility_aliases(self):
        asset_root = PLUGIN_ROOT / "skills" / "onion-image" / "assets"
        manifest = json.loads((asset_root / "asset-manifest.json").read_text(encoding="utf-8"))
        logos = [asset for asset in manifest["assets"] if asset.get("kind") == "logo"]

        self.assertEqual(
            [asset["asset_id"] for asset in logos],
            ["logo.onion.standard.001", "logo.onion.app.001"],
        )
        app_logo = next(asset for asset in logos if asset["asset_id"] == "logo.onion.app.001")
        self.assertEqual(app_logo["path"], "assets/logos/onion-logo-app-001.png")
        self.assertNotIn("legacy_path", app_logo)

        approved_logo = PLUGIN_ROOT / "skills" / "onion-image" / app_logo["path"]
        self.assertEqual(
            hashlib.sha256(approved_logo.read_bytes()).hexdigest(),
            "35ba4b2fc718003244b844373bc3cb89da015d206babc2a36c1fa938fb1fa387",
        )
        self.assertFalse((asset_root / "logos" / "onion-logo-app-001-hd-navy.png").exists())
        aliases = {
            "洋葱学园+APP.png": approved_logo,
            "洋葱学园.png": asset_root / "logos" / "onion-logo-standard-001.png",
        }
        for alias_name, canonical_path in aliases.items():
            alias_path = asset_root / "logos" / alias_name
            self.assertTrue(alias_path.is_file(), alias_name)
            self.assertEqual(alias_path.read_bytes(), canonical_path.read_bytes(), alias_name)
        self.assertFalse(any("legacy_path" in asset for asset in logos))

    def test_input_json_labeled_references_validate_and_echo_labels(self):
        env = dict(os.environ)
        env.pop("LAOZHANG_API_KEY", None)
        with tempfile.TemporaryDirectory() as tmp:
            input_json = Path(tmp) / "render-input.json"
            input_json.write_text(
                json.dumps(
                    {
                        "prompt": "参考图说明：参考图1 是品牌 Logo；参考图2 是豆包正常版角色。左上角原样呈现参考图1的完整 Logo，图形、文字、颜色、比例、轮廓及角标均与原图一致，不得重绘、变形、简化或拆分；Logo直接融入画面原有背景，周围延续整体色调，不另加底板、色块、边框或弧形区域，仅调整整体大小和位置。参考图2站在屏幕旁。",
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

    def test_logo_asset_path_must_match_manifest(self):
        reference_items = self.render.normalize_reference_items(
            [
                {
                    "label": "参考图1",
                    "role": "品牌 Logo 参考图",
                    "asset_id": "logo.onion.app.001",
                    "path": "assets/logos/onion-logo-standard-001.png",
                }
            ]
        )

        with self.assertRaisesRegex(ValueError, "asset_id.*path.*不匹配"):
            self.render.validate_asset_reference_bindings(reference_items)

    def test_structured_logo_reference_requires_exact_preservation_rule(self):
        reference_items = self.render.normalize_reference_items(
            [
                {
                    "label": "参考图1",
                    "role": "品牌 Logo 参考图",
                    "asset_id": "logo.onion.app.001",
                    "path": "assets/logos/onion-logo-app-001.png",
                }
            ]
        )

        with self.assertRaisesRegex(ValueError, "Logo 保真约束"):
            self.render.validate_logo_prompt_rule(
                "参考图说明：参考图1 是品牌 Logo。左上角放参考图1。",
                reference_items,
            )

    def test_logo_prompt_rule_forbids_redrawing_and_protects_clear_space(self):
        expected = (
            "左上角原样呈现参考图1的完整 Logo，图形、文字、颜色、比例、轮廓及角标均与原图一致，"
            "不得重绘、变形、简化或拆分；Logo直接融入画面原有背景，周围延续整体色调，"
            "不另加底板、色块、边框或弧形区域，仅调整整体大小和位置。"
        )

        self.assertEqual(self.render.logo_prompt_rule(), expected)

    def test_old_logo_prompt_rule_is_no_longer_accepted(self):
        reference_items = self.render.normalize_reference_items(
            [
                {
                    "label": "参考图1",
                    "role": "品牌 Logo 参考图",
                    "asset_id": "logo.onion.app.001",
                    "path": "assets/logos/onion-logo-app-001.png",
                }
            ]
        )
        old_rule = (
            "左上角完整使用参考图1的 Logo，图形、文字、颜色和比例均不得改变，"
            "不得拆分或只保留头像；通过大小、边距、留白和背景对比使其清晰自然、不抢主视觉。"
        )

        with self.assertRaisesRegex(ValueError, "Logo 保真约束"):
            self.render.validate_logo_prompt_rule(old_rule, reference_items)

    def test_logo_prompt_rejects_conflicting_local_background_panel_instruction(self):
        reference_items = self.render.normalize_reference_items(
            [
                {
                    "label": "参考图1",
                    "role": "品牌 Logo 参考图",
                    "asset_id": "logo.onion.app.001",
                    "path": "assets/logos/onion-logo-app-001.png",
                }
            ]
        )
        prompt = (
            self.render.logo_prompt_rule()
            + "左上角Logo区域使用稳定的品牌蓝局部底色形成清晰对比。"
        )

        with self.assertRaisesRegex(ValueError, "Logo 背景指令冲突"):
            self.render.validate_logo_prompt_rule(prompt, reference_items)

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
                "测试 prompt。左上角原样呈现参考图1的完整 Logo，图形、文字、颜色、比例、轮廓及角标均与原图一致，不得重绘、变形、简化或拆分；Logo直接融入画面原有背景，周围延续整体色调，不另加底板、色块、边框或弧形区域，仅调整整体大小和位置。",
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

    def test_cli_defaults_to_high_quality(self):
        env = dict(os.environ)
        env.pop("LAOZHANG_API_KEY", None)
        output = subprocess.run(
            [
                sys.executable,
                str(RENDER_PATH),
                "--prompt",
                "测试 prompt",
                "--size",
                "1024x1024",
                "--output",
                str(Path(tempfile.gettempdir()) / "onion-render-default-quality-test.png"),
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
        self.assertEqual(payload["quality"], "high")

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
