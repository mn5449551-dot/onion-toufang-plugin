import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATHS = PLUGIN_ROOT / "shared" / "scripts" / "runtime_paths.py"


def load_runtime_paths_module():
    spec = importlib.util.spec_from_file_location("runtime_paths", RUNTIME_PATHS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuntimePathsTests(unittest.TestCase):
    def test_default_output_root_preserves_posix_tmp_dir(self):
        module = load_runtime_paths_module()

        with mock.patch.dict(os.environ, {}, clear=True):
            root = module.output_root()

        self.assertEqual(root, Path("/tmp/onion-ad").resolve())

    def test_windows_default_output_root_uses_system_temp_dir(self):
        module = load_runtime_paths_module()

        with mock.patch.object(module.platform, "system", return_value="Windows"):
            root = module.default_output_root()

        self.assertEqual(root, (Path(tempfile.gettempdir()) / "onion-ad").resolve())

    def test_output_root_can_be_overridden(self):
        module = load_runtime_paths_module()

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"ONION_AD_OUTPUT_ROOT": tmp}, clear=True):
                root = module.output_root()

            self.assertEqual(root, Path(tmp).resolve())

    def test_request_output_dir_is_under_runtime_root(self):
        module = load_runtime_paths_module()

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"ONION_AD_OUTPUT_ROOT": tmp}, clear=True):
                output_dir = module.request_output_dir("req-001")

            self.assertEqual(output_dir, Path(tmp).resolve() / "req-001")


if __name__ == "__main__":
    unittest.main()
