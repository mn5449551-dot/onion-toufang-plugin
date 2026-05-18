import json
from pathlib import Path
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
EVALS_PATH = PLUGIN_ROOT / "behavior-evals" / "critical-flows.json"


class BehaviorEvalManifestTests(unittest.TestCase):
    def test_critical_flow_evals_cover_recent_failure_modes(self):
        payload = json.loads(EVALS_PATH.read_text(encoding="utf-8"))
        cases = {case["id"]: case for case in payload["evals"]}

        required = {
            "direction-id-cannot-start-image",
            "ambiguous-second-choice",
            "direction-choice-then-image-needs-copy",
            "multi-direction-copy-scope",
            "image-must-open-config",
            "oral-set-selection-cannot-write-base",
            "uploaded-app-screenshot-stays-new-image",
            "uploaded-old-ad-routes-iterate",
            "missing-api-key-routes-help",
        }
        self.assertEqual(set(cases), required)
        for case in cases.values():
            self.assertIn("prompt", case)
            self.assertIn("expected_behavior", case)
            self.assertIn("must_not", case)
            self.assertIsInstance(case["must_not"], list)

        self.assertIn("onion-copy", cases["direction-id-cannot-start-image"]["expected_behavior"])
        self.assertIn("不能打开图片配置页", cases["direction-id-cannot-start-image"]["must_not"])
        self.assertIn("先启动图片配置页", cases["image-must-open-config"]["expected_behavior"])
        self.assertIn("不能写 Base", cases["oral-set-selection-cannot-write-base"]["expected_behavior"])
        self.assertIn("onion-image-iterate", cases["uploaded-old-ad-routes-iterate"]["expected_behavior"])


if __name__ == "__main__":
    unittest.main()
