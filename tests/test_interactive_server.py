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
        self.assertIn("target_size", html)
        self.assertIn("render_size", html)
        self.assertIn("disabled_reason", html)
        self.assertIn('type="number"', html)
        self.assertIn("thumb-card", html)
        self.assertIn("fontEnabled", html)
        self.assertIn("ui_reference_note", html)
        self.assertIn("generation_mode", html)
        self.assertNotIn("__DATA_JSON__", html)
        self.assertNotIn("{{", html)

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
                def post(endpoint, payload):
                    url = f"http://127.0.0.1:{httpd.server_port}{endpoint}"
                    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
                    with request.urlopen(req, timeout=5) as response:
                        return json.loads(response.read().decode("utf-8"))

                config_payload = post("/api/image-config", {"request_id": "req-test", "sets": 2})
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
            self.assertEqual(selection["schemes"], [])
            self.assertEqual(image_sets["sets"][0]["set_id"], "set1")
            self.assertEqual(live_sets_payload["sets"][0]["thumb"], ["set1_img1.png"])
            self.assertEqual(logo_status, 200)

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
