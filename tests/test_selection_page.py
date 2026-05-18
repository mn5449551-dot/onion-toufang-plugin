import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BUILD_SELECTION_PATH = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "build_selection_page.py"


def load_builder_module():
    spec = importlib.util.spec_from_file_location("onion_build_selection", BUILD_SELECTION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SelectionPageTests(unittest.TestCase):
    def setUp(self):
        self.builder = load_builder_module()

    def test_normalizes_image_group_shape_to_template_sets(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            image = out_dir / "set1_img1.png"
            image.write_bytes(b"fake")
            request_id, sets = self.builder.normalize_sets(
                {
                    "request_id": "req-test",
                    "schemes": [
                        {
                            "id": "set1",
                            "images": [{"index": 1, "path": str(image)}],
                            "渠道": "应用商店",
                            "图片形式": "单图",
                            "比例": "1:1",
                            "IP形象": "豆包",
                            "copy_id": "C-001",
                            "copy_summary": "洋葱一拍，解析秒出",
                        }
                    ],
                },
                out_dir,
            )

        self.assertEqual(request_id, "req-test")
        self.assertEqual(sets[0]["set_id"], "set1")
        self.assertEqual(sets[0]["thumb"], ["set1_img1.png"])
        self.assertEqual(sets[0]["meta"]["channel"], "应用商店")
        self.assertEqual(sets[0]["source"]["copyId"], "C-001")

    def test_copies_external_absolute_images_next_to_html(self):
        with tempfile.TemporaryDirectory() as source_tmp, tempfile.TemporaryDirectory() as out_tmp:
            source_dir = Path(source_tmp)
            out_dir = Path(out_tmp)
            image = source_dir / "set1_img1.png"
            image.write_bytes(b"fake")
            _, sets = self.builder.normalize_sets(
                {
                    "request_id": "req-test",
                    "schemes": [{"id": "set1", "images": [{"index": 1, "path": str(image)}]}],
                },
                out_dir,
            )

            thumb = sets[0]["thumb"][0]
            copied = out_dir / thumb
            self.assertTrue(thumb.startswith("selection-assets/"))
            self.assertTrue(copied.is_file())
            self.assertEqual(copied.read_bytes(), b"fake")

    def test_cli_writes_html_with_embedded_sets_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            image = out_dir / "set1_img1.png"
            image.write_bytes(b"fake")
            data = out_dir / "sets.json"
            data.write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "schemes": [{"id": "set1", "images": [{"path": str(image)}]}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            html = out_dir / "image-selection.html"
            result = subprocess.run(
                [
                    sys.executable,
                    str(BUILD_SELECTION_PATH),
                    "--sets-data",
                    str(data),
                    "--output",
                    str(html),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertIn("image_sets", payload)
            text = html.read_text(encoding="utf-8")
            image_sets = json.loads((out_dir / "image-sets.json").read_text(encoding="utf-8"))
            self.assertIn("req-test", text)
            self.assertIn('"thumb": ["set1_img1.png"]', text)
            self.assertEqual(image_sets["sets"][0]["set_id"], "set1")
            self.assertIn("/api/image-selection", text)
            self.assertIn("/api/image-sets", text)
            self.assertIn("accepted_schemes", text)
            self.assertIn("Only accepted_schemes may be written to Feishu", text)
            self.assertIn("标注结果已保存", text)
            self.assertIn("回到当前 AI 对话回复：好了", text)
            self.assertNotIn("clipboard.writeText", text)
            self.assertNotIn("复制下面的 JSON", text)
            self.assertNotIn("粘贴回 Claude Code", text)
            self.assertNotIn("{{SETS_DATA}}", text)


if __name__ == "__main__":
    unittest.main()
