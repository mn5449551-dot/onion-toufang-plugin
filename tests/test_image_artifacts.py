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
            Image.new("RGB", (200, 120), (80, 120, 240)).save(root / "set1_img1.png")
            Image.new("RGB", (200, 120), (240, 80, 80)).save(root / "set2_img1.png")
            (root / "image-config-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "delivery_name": "方向31",
                        "placements": [
                            {
                                "id": "huawei-big-card",
                                "category": "应用商店",
                                "platform": "华为",
                                "placement": "大卡智投",
                                "target_size": "1280x720",
                                "target_width": 1280,
                                "target_height": 720,
                                "max_file_size_kb": 150,
                                "image_form": "单图",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result_path = root / "image-selection-result.json"
            result_path.write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "accepted_schemes": [
                            {
                                "set_id": "set1",
                                "thumb": ["set1_img1.png"],
                                "placement_id": "huawei-big-card",
                                "meta": {"channel": "应用商店", "platform": "华为", "placement": "大卡智投"},
                                "source": {"copyId": "C-003", "copyRecordId": "recCopy003"},
                            }
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

            result = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_SCRIPT),
                    "--selection-result",
                    str(result_path),
                    "--target-kb",
                    "150",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["accepted_count"], 1)
            output = root / "方向31.zip"
            self.assertEqual(payload["zip"], str(output.resolve()))
            self.assertEqual(payload["manifest_path"], str((root / "方向31-manifest.json").resolve()))
            self.assertEqual(payload["manifest"]["delivery_name"], "方向31")
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn("方向31-应用商店-华为-大卡智投/方向31-应用商店-华为-大卡智投-1.jpg", names)
                self.assertNotIn("manifest.json", names)
                self.assertNotIn("set2/img1.png", names)
            manifest = json.loads((root / "方向31-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["delivery_name"], "方向31")
            self.assertEqual(manifest["delivery_name_safe"], "方向31")
            self.assertEqual(manifest["schemes"][0]["set_id"], "set1")
            self.assertEqual(manifest["schemes"][0]["copy_id"], "C-003")
            self.assertEqual(manifest["schemes"][0]["copy_record_id"], "recCopy003")
            self.assertEqual(manifest["schemes"][0]["files"][0]["zip_path"], "方向31-应用商店-华为-大卡智投/方向31-应用商店-华为-大卡智投-1.jpg")

    def test_package_accepted_images_uses_standard_archive_names_with_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.new("RGB", (200, 100), (80, 120, 240)).save(source)
            (root / "image-config-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "delivery_name": "方向31",
                        "placements": [
                            {
                                "id": "huawei-big-card",
                                "category": "应用商店",
                                "platform": "华为",
                                "placement": "大卡智投",
                                "target_size": "120x80",
                                "target_width": 120,
                                "target_height": 80,
                                "max_file_size_kb": 100,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result_path = root / "image-selection-result.json"
            result_path.write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "accepted_schemes": [
                            {
                                "set_id": "Set 1",
                                "thumb": ["source.png"],
                                "placement_id": "huawei-big-card",
                                "target_width": 120,
                                "target_height": 80,
                                "target_kb": 100,
                                "meta": {"category": "应用商店", "platform": "华为", "placement": "大卡智投"},
                                "source": {"copyId": "C-101"},
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
            self.assertEqual(names, ["方向31-应用商店-华为-大卡智投/方向31-应用商店-华为-大卡智投-1.jpg"])

    def test_delivery_name_strips_zip_suffix_and_cleans_unsafe_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (60, 60), (80, 120, 240)).save(root / "source.png")
            (root / "image-config-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "delivery_name": "方向/31:测试.zip",
                        "placements": [
                            {
                                "id": "slot1",
                                "category": "信息流",
                                "platform": "趣头条",
                                "placement": "横版大图",
                                "target_size": "1280x720",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result_path = root / "image-selection-result.json"
            result_path.write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "accepted_schemes": [
                            {
                                "set_id": "set1",
                                "thumb": ["source.png"],
                                "placement_id": "slot1",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(PACKAGE_SCRIPT),
                    "--selection-result",
                    str(result_path),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["zip"], str((root / "方向-31-测试.zip").resolve()))
            with zipfile.ZipFile(root / "方向-31-测试.zip") as archive:
                self.assertEqual(
                    archive.namelist(),
                    ["方向-31-测试-信息流-趣头条-横版大图/方向-31-测试-信息流-趣头条-横版大图-1.jpg"],
                )

    def test_package_failure_does_not_leave_partial_zip_or_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.png").write_text("not an image", encoding="utf-8")
            (root / "image-config-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "delivery_name": "方向31",
                        "placements": [
                            {
                                "id": "slot1",
                                "category": "信息流",
                                "platform": "趣头条",
                                "placement": "横版大图",
                                "target_size": "1280x720",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result_path = root / "image-selection-result.json"
            result_path.write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "accepted_schemes": [
                            {"set_id": "set1", "thumb": ["bad.png"], "placement_id": "slot1"}
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(PACKAGE_SCRIPT), "--selection-result", str(result_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "方向31.zip").exists())
            self.assertFalse((root / "方向31-manifest.json").exists())

    def test_same_placement_name_with_different_size_adds_size_to_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (80, 80), (80, 120, 240)).save(root / "a.png")
            Image.new("RGB", (80, 80), (240, 120, 80)).save(root / "b.png")
            (root / "image-config-result.json").write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "delivery_name": "方向31",
                        "placements": [
                            {"id": "slot-a", "category": "应用商店", "platform": "华为", "placement": "大卡智投", "target_size": "1280x720"},
                            {"id": "slot-b", "category": "应用商店", "platform": "华为", "placement": "大卡智投", "target_size": "640x360"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result_path = root / "image-selection-result.json"
            result_path.write_text(
                json.dumps(
                    {
                        "request_id": "req-test",
                        "accepted_schemes": [
                            {"set_id": "set1", "thumb": ["a.png"], "placement_id": "slot-a"},
                            {"set_id": "set2", "thumb": ["b.png"], "placement_id": "slot-b"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [sys.executable, str(PACKAGE_SCRIPT), "--selection-result", str(result_path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )

            with zipfile.ZipFile(root / "方向31.zip") as archive:
                self.assertEqual(
                    archive.namelist(),
                    [
                        "方向31-应用商店-华为-大卡智投-1280x720/方向31-应用商店-华为-大卡智投-1280x720-1.jpg",
                        "方向31-应用商店-华为-大卡智投-640x360/方向31-应用商店-华为-大卡智投-640x360-1.jpg",
                    ],
                )

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
