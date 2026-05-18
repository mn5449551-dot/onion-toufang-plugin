import json
import importlib.util
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
WRITE_IMAGE_GROUP_SCRIPT = PLUGIN_ROOT / "shared" / "scripts" / "write_image_group.py"


def load_write_image_group_module():
    shared_scripts = str(PLUGIN_ROOT / "shared" / "scripts")
    if shared_scripts not in sys.path:
        sys.path.insert(0, shared_scripts)
    spec = importlib.util.spec_from_file_location("write_image_group", WRITE_IMAGE_GROUP_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            self.assertEqual(payload["zip"], str(output.resolve()))
            self.assertEqual(payload["manifest_path"], str((root / "accepted-manifest.json").resolve()))
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn("set01_set1/set01_img01.png", names)
                self.assertNotIn("manifest.json", names)
                self.assertNotIn("set2/img1.png", names)
            manifest = json.loads((root / "accepted-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schemes"][0]["set_id"], "set1")
            self.assertEqual(manifest["schemes"][0]["files"][0]["zip_path"], "set01_set1/set01_img01.png")

    def test_package_accepted_images_uses_standard_archive_names_with_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.new("RGB", (200, 100), (80, 120, 240)).save(source)
            result_path = root / "image-selection-result.json"
            result_path.write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "accepted_schemes": [
                            {
                                "set_id": "Set 1 / 应用商店",
                                "thumb": ["source.png"],
                                "target_width": 120,
                                "target_height": 80,
                                "target_kb": 100,
                            }
                        ],
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
                    "--target-kb",
                    "100",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
            self.assertEqual(names, ["set01_set-1/set01_img01_120x80_100kb.jpg"])

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

    def test_write_image_group_preserves_relationship_fields_over_metadata(self):
        module = load_write_image_group_module()

        fields = module.build_record_fields(
            direction_id="recDirection",
            copy_id="recCopy",
            parent_group_id="recParent",
            metadata={
                "关联方向": ["badDirection"],
                "关联文案": ["badCopy"],
                "父图组": ["badParent"],
                "渠道": "信息流",
            },
            images=[],
        )

        self.assertEqual(fields["关联方向"], ["recDirection"])
        self.assertEqual(fields["关联文案"], ["recCopy"])
        self.assertEqual(fields["父图组"], ["recParent"])
        self.assertEqual(fields["渠道"], "信息流")

    def test_write_image_group_dry_run_accepts_package_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "set1.png"
            package = root / "req-test-accepted-images.zip"
            image.write_bytes(b"fake")
            package.write_bytes(b"zip")

            result = subprocess.run(
                [
                    sys.executable,
                    str(WRITE_IMAGE_GROUP_SCRIPT),
                    "--images",
                    json.dumps([{"index": 1, "path": str(image)}], ensure_ascii=False),
                    "--metadata",
                    json.dumps({"渠道": "信息流"}, ensure_ascii=False),
                    "--package-zip",
                    str(package),
                    "--dry-run",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["package_zip"], str(package.resolve()))


if __name__ == "__main__":
    unittest.main()
