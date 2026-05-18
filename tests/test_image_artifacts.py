import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

from PIL import Image


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "package_accepted_images.py"
CLEANUP_SCRIPT = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "cleanup_image_outputs.py"
COMPRESS_SCRIPT = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "image_compress.py"


class ImageArtifactTests(unittest.TestCase):
    def test_package_accepted_images_zips_only_accepted_schemes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "set1_img1.png").write_bytes(b"accepted-1")
            (root / "set2_img1.png").write_bytes(b"rejected-1")
            result_path = root / "image-selection-result.json"
            result_path.write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "accepted_schemes": [
                            {"set_id": "set1", "thumb": ["set1_img1.png"], "meta": {"channel": "应用商店"}}
                        ],
                        "rejected_schemes": [
                            {"set_id": "set2", "thumb": ["set2_img1.png"]}
                        ],
                        "pending_scheme_ids": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            output = root / "accepted.zip"

            result = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_SCRIPT),
                    "--selection-result",
                    str(result_path),
                    "--output",
                    str(output),
                    "--no-compress",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["accepted_count"], 1)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn("set1/img1.png", names)
                self.assertIn("manifest.json", names)
                self.assertNotIn("set2/img1.png", names)
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            self.assertEqual(manifest["schemes"][0]["set_id"], "set1")

    def test_cleanup_image_outputs_deletes_only_old_original_pngs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_png = root / "old.png"
            new_png = root / "new.png"
            compressed = root / "old.compressed-200kb.jpg"
            package = root / "accepted.zip"
            for path in (old_png, new_png, compressed, package):
                path.write_bytes(b"data")
            old_time = time.time() - 9 * 24 * 60 * 60
            os.utime(old_png, (old_time, old_time))

            result = subprocess.run(
                [
                    sys.executable,
                    str(CLEANUP_SCRIPT),
                    "--root",
                    str(root),
                    "--original-retention-days",
                    "7",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertFalse(old_png.exists())
            self.assertTrue(new_png.exists())
            self.assertTrue(compressed.exists())
            self.assertTrue(package.exists())
            self.assertEqual(payload["deleted_count"], 1)

    def test_image_compress_can_export_exact_target_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            output = root / "output.jpg"
            Image.new("RGB", (400, 200), (240, 80, 80)).save(source)

            result = subprocess.run(
                [
                    sys.executable,
                    str(COMPRESS_SCRIPT),
                    str(source),
                    str(output),
                    "--target-kb",
                    "100",
                    "--target-width",
                    "120",
                    "--target-height",
                    "80",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            self.assertIn("120x80", result.stdout)
            with Image.open(output) as exported:
                self.assertEqual(exported.size, (120, 80))


if __name__ == "__main__":
    unittest.main()
