import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib import request


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "interactive_server.py"


def load_server_module():
    spec = importlib.util.spec_from_file_location("onion_interactive_server", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InteractiveServerTests(unittest.TestCase):
    def setUp(self):
        self.server = load_server_module()

    def test_loads_ai_ad_platform_slots_with_ratio_and_kb(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules = Path(tmp) / "platform-rules.json"
            rules.write_text(
                json.dumps(
                    {
                        "platforms": [
                            {
                                "id": "oppo",
                                "name": "OPPO",
                                "slots": [
                                    {
                                        "id": "oppo_double",
                                        "name": "横版两图",
                                        "channel": "app_store",
                                        "imageForm": "double",
                                        "targetRatio": "r_9_16",
                                        "targetWidth": 474,
                                        "targetHeight": 768,
                                        "maxFileSizeKb": 150,
                                    }
                                ],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            slots = self.server.load_platform_slots(rules)

        self.assertEqual(slots[0]["platform"], "OPPO")
        self.assertEqual(slots[0]["channel"], "应用商店")
        self.assertEqual(slots[0]["imageForm"], "双图")
        self.assertEqual(slots[0]["ratio"], "9:16")
        self.assertEqual(slots[0]["maxFileSizeKb"], 150)

    def test_config_payload_includes_real_ip_assets_and_font_references(self):
        payload = self.server.build_config_payload("req-test")

        self.assertGreaterEqual(len(payload["slots"]), 1)
        self.assertGreaterEqual(len(payload["ipOptions"]), 2)
        self.assertGreaterEqual(len(payload["logoOptions"]), 2)
        self.assertEqual(payload["ipOptions"][0]["label"], "不用 IP")
        self.assertEqual(payload["ipOptions"][1]["value"], "随机")
        self.assertTrue(payload["ipOptions"][1]["random"])
        self.assertTrue(payload["logoOptions"][1]["thumb"].startswith("/skill-assets/assets/logos/"))
        self.assertTrue(payload["ipOptions"][2]["thumb"].startswith("/skill-assets/assets/ip-roles/"))
        self.assertEqual(len(payload["fontOptions"]), 31)
        self.assertTrue(payload["fontOptions"][0]["path"].startswith("assets/font-references/"))
        self.assertIn("百度", payload["categories"])

    def test_config_html_contains_submit_endpoint_and_font_rule(self):
        html = self.server.build_config_html(self.server.build_config_payload("req-test"))

        self.assertIn("/api/image-config", html)
        self.assertIn("图片生成配置", html)
        self.assertIn("font_prompt_rule", html)
        self.assertIn("category-tabs", html)
        self.assertIn("selectedSlotIds", html)
        self.assertIn("toggleSlot", html)
        self.assertIn("请先选择至少一个版位", html)
        self.assertIn("target_size", html)
        self.assertIn("render_size", html)
        self.assertIn("disabled_reason", html)
        self.assertIn('type="number"', html)
        self.assertIn("thumb-card", html)
        self.assertIn("fontEnabled", html)
        self.assertIn("ui_reference_note", html)
        self.assertIn("uiReferenceRequired", html)
        self.assertIn("画面需要展示洋葱 APP 界面/功能截图", html)
        self.assertIn("手机、学习机或其它电子屏幕", html)
        self.assertIn("保存后请回到 Codex 上传截图", html)
        self.assertIn("generation_mode", html)
        self.assertIn("保存配置", html)
        self.assertIn("回到 Codex 回复：好了", html)
        self.assertNotIn("复制 JSON", html)
        self.assertNotIn("copyResult", html)
        self.assertNotIn("__DATA_JSON__", html)
        self.assertNotIn("{{", html)

    def test_config_html_uses_external_template_file(self):
        template_path = PLUGIN_ROOT / "skills" / "onion-image" / "templates" / "image-config.html"

        self.assertTrue(template_path.exists())
        template = template_path.read_text(encoding="utf-8")
        self.assertIn("__REQUEST_ID__", template)
        self.assertIn("__DATA_JSON__", template)
        self.assertIn("/api/image-config", template)
        self.assertIn("DATA.desiredChannels", template)
        self.assertNotIn("复制 JSON", template)
        self.assertNotIn("copyResult", template)
        self.assertNotIn("first) state.selectedSlotIds", template)

        html = self.server.build_config_html(self.server.build_config_payload("req-test"))

        self.assertNotIn("__REQUEST_ID__", html)
        self.assertNotIn("__DATA_JSON__", html)
        self.assertIn("Request req-test", html)

    def test_post_writes_image_config_selection_and_live_sets_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            image = output_dir / "set1_img1.png"
            image.write_bytes(b"fake")
            httpd = self.server.OnionInteractionServer(
                ("127.0.0.1", 0),
                output_dir=output_dir,
                request_id="req-test",
                context={},
                platform_rules=None,
            )
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                slot_id = next(slot["id"] for slot in self.server.load_platform_slots() if slot.get("enabled"))

                def post(endpoint, payload):
                    url = f"http://127.0.0.1:{httpd.server_port}{endpoint}"
                    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
                    with request.urlopen(req, timeout=5) as response:
                        return json.loads(response.read().decode("utf-8"))

                config_payload = post("/api/image-config", {"request_id": "req-test", "sets": 2, "placement_ids": [slot_id]})
                selection_payload = post("/api/image-selection", {"request_id": "req-test", "schemes": []})
                sets_payload = post(
                    "/api/image-sets",
                    {
                        "request_id": "req-test",
                        "schemes": [{"id": "set1", "images": [{"path": str(image)}]}],
                    },
                )
                with request.urlopen(f"http://127.0.0.1:{httpd.server_port}/api/image-sets", timeout=5) as response:
                    live_sets_payload = json.loads(response.read().decode("utf-8"))
                with request.urlopen(f"http://127.0.0.1:{httpd.server_port}/skill-assets/assets/logos/onion-logo-standard-001.png", timeout=5) as response:
                    logo_status = response.status
                    response.read()
            finally:
                httpd.shutdown()
                thread.join(timeout=5)
                httpd.server_close()

            self.assertTrue(config_payload["ok"])
            self.assertTrue(selection_payload["ok"])
            self.assertTrue(sets_payload["ok"])
            config = json.loads((output_dir / "image-config-result.json").read_text(encoding="utf-8"))
            selection = json.loads((output_dir / "image-selection-result.json").read_text(encoding="utf-8"))
            image_sets = json.loads((output_dir / "image-sets.json").read_text(encoding="utf-8"))
            self.assertEqual(config["sets"], 2)
            self.assertFalse(config["ui_reference_required"])
            self.assertFalse(config["screen_ui_reference_required"])
            self.assertEqual(selection["schemes"], [])
            self.assertEqual(image_sets["sets"][0]["set_id"], "set1")
            self.assertEqual(live_sets_payload["sets"][0]["thumb"], ["set1_img1.png"])
            self.assertEqual(logo_status, 200)

    def test_static_file_paths_cannot_escape_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "output"
            output_dir.mkdir()
            httpd = self.server.OnionInteractionServer(
                ("127.0.0.1", 0),
                output_dir=output_dir,
                request_id="req-test",
                context={},
                platform_rules=None,
            )
            handler = object.__new__(self.server.OnionInteractionHandler)
            handler.server = httpd

            translated = Path(handler.translate_path("/../secret.txt")).resolve()

            self.assertEqual(translated, (output_dir / "__forbidden__").resolve())
            httpd.server_close()

    def test_config_result_requires_explicit_placement_selection(self):
        slots = self.server.load_platform_slots()
        by_id = {slot["id"]: slot for slot in slots}

        with self.assertRaisesRegex(ValueError, "select at least one enabled placement"):
            self.server.normalize_config_result({"request_id": "req-test", "sets": 2}, by_id)

    def test_ui_reference_required_is_persisted_as_blocking_codex_upload(self):
        slots = self.server.load_platform_slots()
        by_id = {slot["id"]: slot for slot in slots}
        slot_id = next(slot["id"] for slot in slots if slot.get("enabled"))
        result = self.server.normalize_config_result(
            {
                "request_id": "req-test",
                "placement_ids": [slot_id],
                "screen_ui_reference_required": True,
                "ui_reference_upload_status": "awaiting_codex_upload",
            },
            by_id,
        )

        self.assertTrue(result["ui_reference_required"])
        self.assertTrue(result["screen_ui_reference_required"])
        self.assertEqual(result["ui_reference_trigger"], "recognizable_onion_app_screen")
        self.assertEqual(result["ui_reference_upload_status"], "awaiting_codex_upload")
        self.assertEqual(result["ui_reference"], "codex_upload_required")
        self.assertIn("上传截图", result["ui_reference_next_action"])
        self.assertIn("弱化/模糊屏幕", result["ui_reference_next_action"])

    def test_iterate_config_mode_preserves_iteration_contract(self):
        payload = self.server.build_config_payload(
            "req-iterate",
            context={
                "generation_mode": "iterate",
                "image_group_id": "G-005",
                "image_form": "三图",
            },
        )
        html = self.server.build_config_html(payload)
        slots = self.server.load_platform_slots()
        by_id = {slot["id"]: slot for slot in slots}
        slot_id = next(slot["id"] for slot in slots if slot.get("enabled"))

        result = self.server.normalize_config_result(
            {
                "request_id": "req-iterate",
                "generation_mode": "iterate",
                "iteration_mode": "expand_similar",
                "base": {
                    "source": "base_group",
                    "image_group_id": "G-005",
                    "image_form": "三图",
                    "image_count": 3,
                },
                "uploaded_image_role": "owned_old_ad",
                "inherit": {"placement": True, "image_form": True},
                "change_axes": ["ip", "scene"],
                "per_image_notes": {"image_1": "保留开头钩子"},
                "placement_ids": [slot_id],
            },
            by_id,
        )

        self.assertEqual(payload["generationMode"], "iterate")
        self.assertIn("图片迭代配置", html)
        self.assertIn("iteration_mode", html)
        self.assertEqual(result["generation_mode"], "iterate")
        self.assertEqual(result["iteration_mode"], "expand_similar")
        self.assertEqual(result["base"]["image_group_id"], "G-005")
        self.assertEqual(result["uploaded_image_role"], "owned_old_ad")
        self.assertEqual(result["iteration"]["change_axes"], ["ip", "scene"])
        self.assertTrue(result["iteration"]["inherit"]["placement"])

    def test_default_rules_include_latest_directness_and_disabled_slots(self):
        slots = self.server.load_platform_slots()
        by_id = {slot["id"]: slot for slot in slots}

        self.assertIn("huawei-app-daily-featured-explore-cover", by_id)
        self.assertEqual(by_id["huawei-app-daily-featured-explore-cover"]["category"], "应用商店")
        self.assertEqual(by_id["huawei-app-daily-featured-explore-cover"]["target_size"], "1280x720")
        self.assertEqual(by_id["huawei-app-daily-featured-explore-cover"]["render_size"], "1280x720")
        self.assertTrue(by_id["huawei-app-daily-featured-explore-cover"]["enabled"])

        self.assertIn("vivo-union-banner-1080x170", by_id)
        self.assertFalse(by_id["vivo-union-banner-1080x170"]["enabled"])
        self.assertEqual(by_id["vivo-union-banner-1080x170"]["directness"], "composite")
        self.assertIn("一期", by_id["vivo-union-banner-1080x170"]["disabled_reason"])

        self.assertEqual(by_id["oppo-bid-banner-1280x720"]["logo_policy"], "forbidden")
        self.assertTrue(by_id["oppo-app-slot-slot-474x768"]["enabled"])
        self.assertEqual(by_id["oppo-app-slot-slot-474x768"]["imageForm"], "双图")
        self.assertTrue(by_id["oppo-app-slot-slot-320x210"]["enabled"])
        self.assertEqual(by_id["oppo-app-slot-slot-320x210"]["imageForm"], "三图")

    def test_context_image_form_temporarily_disables_mismatched_slots(self):
        single_payload = self.server.build_config_payload("req-test", context={"image_form": "单图"})
        single_by_id = {slot["id"]: slot for slot in single_payload["slots"]}

        self.assertEqual(single_payload["desiredImageForm"], "单图")
        self.assertTrue(single_by_id["oppo-rich-horizontal-big-1280x720"]["enabled"])
        self.assertFalse(single_by_id["oppo-app-slot-slot-474x768"]["enabled"])
        self.assertIn("本次图片形式为单图", single_by_id["oppo-app-slot-slot-474x768"]["disabled_reason"])

        triple_payload = self.server.build_config_payload("req-test", context={"图片形式": "三图"})
        triple_by_id = {slot["id"]: slot for slot in triple_payload["slots"]}

        self.assertEqual(triple_payload["desiredImageForm"], "三图")
        self.assertFalse(triple_by_id["oppo-rich-horizontal-big-1280x720"]["enabled"])
        self.assertTrue(triple_by_id["oppo-app-slot-slot-320x210"]["enabled"])

    def test_copy_text_fields_infer_exact_image_form(self):
        single_payload = self.server.build_config_payload(
            "req-single",
            context={"主标题": "拍一下，先看答案", "副标题": "洋葱逐步讲解，哪步不懂问哪步"},
        )
        double_payload = self.server.build_config_payload(
            "req-double",
            context={"短句1": "拍题秒出解析", "短句2": "不懂继续追问"},
        )
        triple_payload = self.server.build_config_payload(
            "req-triple",
            context={"短句1": "拍一下", "短句2": "看步骤", "短句3": "继续问"},
        )

        self.assertEqual(single_payload["desiredImageForm"], "单图")
        self.assertEqual(double_payload["desiredImageForm"], "双图")
        self.assertEqual(triple_payload["desiredImageForm"], "三图")

    def test_context_channel_temporarily_disables_other_categories(self):
        feed_payload = self.server.build_config_payload("req-feed", context={"渠道": "信息流"})
        feed_by_id = {slot["id"]: slot for slot in feed_payload["slots"]}

        self.assertEqual(feed_payload["desiredChannels"], ["信息流"])
        self.assertTrue(feed_by_id["netease-feed-slot-slot-1280x720"]["enabled"])
        self.assertFalse(feed_by_id["oppo-rich-horizontal-big-1280x720"]["enabled"])
        self.assertIn("本次渠道为信息流", feed_by_id["oppo-rich-horizontal-big-1280x720"]["disabled_reason"])

        learning_payload = self.server.build_config_payload("req-learning", context={"channel": "learning_device"})
        learning_by_id = {slot["id"]: slot for slot in learning_payload["slots"]}

        self.assertEqual(learning_payload["desiredChannels"], ["学习机"])
        self.assertTrue(learning_by_id["readboy-learning-slot-banner-484x580"]["enabled"])
        self.assertFalse(learning_by_id["netease-feed-slot-slot-1280x720"]["enabled"])

    def test_raw_brief_can_lock_channel_and_image_form(self):
        payload = self.server.build_config_payload("req-brief", context={"brief": "应用商店双图，帮我做两套"})
        by_id = {slot["id"]: slot for slot in payload["slots"]}

        self.assertEqual(payload["desiredChannels"], ["应用商店"])
        self.assertEqual(payload["desiredImageForm"], "双图")
        self.assertTrue(by_id["oppo-app-slot-slot-474x768"]["enabled"])
        self.assertFalse(by_id["oppo-rich-horizontal-big-1280x720"]["enabled"])
        self.assertFalse(by_id["netease-feed-slot-slot-1280x720"]["enabled"])

    def test_config_result_rejects_slots_mismatched_with_context(self):
        slots = self.server.constrained_slots_for_context(context={"渠道": "信息流", "图片形式": "单图"})
        by_id = {slot["id"]: slot for slot in slots}

        result = self.server.normalize_config_result(
            {"request_id": "req-test", "placement_ids": ["netease-feed-slot-slot-1280x720"]},
            by_id,
        )
        self.assertEqual(result["channel"], "信息流")
        self.assertEqual(result["image_form"], "单图")

        with self.assertRaisesRegex(ValueError, "placement is disabled"):
            self.server.normalize_config_result(
                {"request_id": "req-test", "placement_ids": ["oppo-rich-horizontal-big-1280x720"]},
                by_id,
            )

    def test_normalizes_selected_multi_placements_for_config_result(self):
        slots = self.server.load_platform_slots()
        by_id = {slot["id"]: slot for slot in slots}
        result = self.server.normalize_config_result(
            {
                "request_id": "req-test",
                "placement_ids": [
                    "oppo-rich-horizontal-big-1280x720",
                    "huawei-app-daily-featured-explore-cover",
                    "netease-feed-slot-slot-1280x720",
                ],
                "sets": 3,
                "ip": "随机",
                "ip_random": True,
            },
            by_id,
        )

        self.assertEqual(result["type"], "image_config")
        self.assertEqual(result["placement_ids"], ["oppo-rich-horizontal-big-1280x720", "huawei-app-daily-featured-explore-cover", "netease-feed-slot-slot-1280x720"])
        self.assertEqual(len(result["placements"]), 3)
        self.assertEqual(result["categories"], ["信息流", "应用商店"])
        self.assertEqual(result["placements"][0]["render_size"], "1280x720")
        self.assertEqual(result["placements"][1]["target_size"], "1280x720")
        self.assertTrue(result["ip_random"])
        self.assertEqual(result["sets"], 3)


if __name__ == "__main__":
    unittest.main()
