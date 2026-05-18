import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PLUGIN_ROOT / "shared" / "scripts"


class BaseScriptTests(unittest.TestCase):
    def run_script(self, script_name, *args, env=None):
        command = [sys.executable, str(SCRIPTS_DIR / script_name), *args]
        result = subprocess.run(
            command,
            cwd=str(PLUGIN_ROOT),
            env=env,
            text=True,
            capture_output=True,
        )
        return result

    def make_env(self, home, fake_lark=None):
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["ONION_BASE_APP_TOKEN"] = "app_token_test"
        if fake_lark is not None:
            env["LARK_CLI_BIN"] = str(fake_lark)
        return env

    def make_fake_lark(self, directory, body):
        fake = Path(directory) / "fake-lark-cli"
        fake.write_text(body, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        return fake

    def pending_path(self, home):
        return Path(home) / ".onion-ad" / "pending.jsonl"

    def read_json_stdout(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_write_record_dry_run_converts_fields_to_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.make_env(tmp)
            result = self.run_script(
                "write_record.py",
                "--table-id",
                "tblLWPSHrZT95oy7",
                "--records",
                '[{"fields":{"素材方向":"方向 A","状态":"待用"}},{"fields":{"状态":"待用","素材方向":"方向 B"}}]',
                "--dry-run",
                env=env,
            )
            payload = self.read_json_stdout(result)

            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["operation"], "record_batch_create")
            self.assertEqual(
                payload["lark_payload"],
                {
                    "fields": ["素材方向", "状态"],
                    "rows": [["方向 A", "待用"], ["方向 B", "待用"]],
                },
            )
            self.assertIn("--as", payload["command"])
            self.assertIn("user", payload["command"])
            self.assertFalse(self.pending_path(tmp).exists())

    def test_write_record_rejects_system_managed_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.make_env(tmp)
            result = self.run_script(
                "write_record.py",
                "--table-id",
                "tblLWPSHrZT95oy7",
                "--records",
                '[{"fields":{"素材方向":"方向 A","创建人":"徐豪","状态":"待用"}}]',
                "--dry-run",
                env=env,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("system-managed", result.stderr)
            self.assertFalse(self.pending_path(tmp).exists())

    def test_update_status_dry_run_emits_record_id_list_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.make_env(tmp)
            result = self.run_script(
                "update_status.py",
                "--table-id",
                "tblLWPSHrZT95oy7",
                "--record-id",
                "recXXX",
                "--status",
                "已用",
                "--dry-run",
                env=env,
            )
            payload = self.read_json_stdout(result)

            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["operation"], "record_batch_update")
            self.assertEqual(
                payload["lark_payload"],
                {"record_id_list": ["recXXX"], "patch": {"状态": "已用"}},
            )
            self.assertFalse(self.pending_path(tmp).exists())

    def test_lookup_record_dry_run_infers_direction_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.make_env(tmp)
            result = self.run_script(
                "lookup_record.py",
                "--id",
                "D-007",
                "--dry-run",
                env=env,
            )
            payload = self.read_json_stdout(result)

            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["table"], "directions")
            self.assertIn("+record-search", payload["lookup_command"])
            self.assertIn("+record-get", payload["get_command"])
            self.assertIn("tblLWPSHrZT95oy7", payload["lookup_command"])

    def test_lookup_record_resolves_business_id_to_record_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.make_fake_lark(
                tmp,
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    args="$*"
                    if echo "$args" | grep -q '+record-search'; then
                      echo '{"data":{"records":[{"record_id":"recDir","fields":{"方向ID":"D-007"}}]}}'
                      exit 0
                    fi
                    if echo "$args" | grep -q '+record-get'; then
                      echo '{"data":{"records":[{"record_id":"recDir","fields":{"方向ID":"D-007","素材方向":"方向 A","状态":"待用"}}]}}'
                      exit 0
                    fi
                    exit 1
                    """
                ),
            )
            env = self.make_env(tmp, fake)
            result = self.run_script("lookup_record.py", "--id", "D-007", env=env)
            payload = self.read_json_stdout(result)

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["table"], "directions")
            self.assertEqual(payload["record_id"], "recDir")
            self.assertEqual(payload["fields"]["素材方向"], "方向 A")

    def test_lookup_record_can_follow_copy_upstream_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.make_fake_lark(
                tmp,
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    args="$*"
                    if echo "$args" | grep -q '+record-search'; then
                      echo '{"data":{"records":[{"record_id":"recCopy","fields":{"文案ID":"C-002"}}]}}'
                      exit 0
                    fi
                    if echo "$args" | grep -q 'tblFdwXSbjANQjlh'; then
                      echo '{"data":{"records":[{"record_id":"recCopy","fields":{"文案ID":"C-002","关联方向":[{"id":"recDir"}],"渠道":"信息流","图片形式":"单图","主标题":"标题 A"}}]}}'
                      exit 0
                    fi
                    if echo "$args" | grep -q 'tblLWPSHrZT95oy7'; then
                      echo '{"data":{"records":[{"record_id":"recDir","fields":{"方向ID":"D-007","素材方向":"方向 A","状态":"已用"}}]}}'
                      exit 0
                    fi
                    exit 1
                    """
                ),
            )
            env = self.make_env(tmp, fake)
            result = self.run_script("lookup_record.py", "--id", "C-002", "--follow-upstream", env=env)
            payload = self.read_json_stdout(result)

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["table"], "copies")
            self.assertEqual(payload["record_id"], "recCopy")
            self.assertEqual(payload["linked"]["directions"][0]["record_id"], "recDir")

    def test_lookup_record_can_follow_image_group_copy_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.make_fake_lark(
                tmp,
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    args="$*"
                    if echo "$args" | grep -q '+record-search'; then
                      echo '{"data":{"records":[{"record_id":"recGroup","fields":{"图组ID":"G-005"}}]}}'
                      exit 0
                    fi
                    if echo "$args" | grep -q 'tblGpuukciptN3PP'; then
                      echo '{"data":{"records":[{"record_id":"recGroup","fields":{"图组ID":"G-005","关联文案":[{"id":"recCopy"}],"渠道":"信息流","图片形式":"单图"}}]}}'
                      exit 0
                    fi
                    if echo "$args" | grep -q 'tblFdwXSbjANQjlh'; then
                      echo '{"data":{"records":[{"record_id":"recCopy","fields":{"文案ID":"C-002","关联方向":[{"id":"recDir"}],"渠道":"信息流","图片形式":"单图","主标题":"标题 A"}}]}}'
                      exit 0
                    fi
                    if echo "$args" | grep -q 'tblLWPSHrZT95oy7'; then
                      echo '{"data":{"records":[{"record_id":"recDir","fields":{"方向ID":"D-007","素材方向":"方向 A","状态":"已用"}}]}}'
                      exit 0
                    fi
                    exit 1
                    """
                ),
            )
            env = self.make_env(tmp, fake)
            result = self.run_script("lookup_record.py", "--id", "G-005", "--follow-upstream", env=env)
            payload = self.read_json_stdout(result)

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["table"], "image_groups")
            self.assertEqual(payload["linked"]["copies"][0]["record_id"], "recCopy")
            self.assertEqual(payload["linked"]["directions"][0]["record_id"], "recDir")

    def test_failing_create_writes_pending_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.make_fake_lark(
                tmp,
                "#!/bin/sh\n"
                "echo 'rate limit 429' >&2\n"
                "exit 1\n",
            )
            env = self.make_env(tmp, fake)
            result = self.run_script(
                "write_record.py",
                "--table-id",
                "tblLWPSHrZT95oy7",
                "--records",
                '[{"fields":{"素材方向":"方向 A","状态":"待用"}}]',
                env=env,
            )

            self.assertEqual(result.returncode, 5)
            pending = self.pending_path(tmp)
            self.assertTrue(pending.exists())
            items = [json.loads(line) for line in pending.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item["schema_version"], 1)
            self.assertEqual(item["op_type"], "record_batch_create")
            self.assertIn("idempotency_key", item)
            self.assertEqual(item["retry_count"], 0)
            self.assertEqual(item["max_retries"], 3)
            self.assertTrue(item["retryable"])
            self.assertFalse(item["ambiguous"])
            self.assertEqual(item["payload"]["table_id"], "tblLWPSHrZT95oy7")
            self.assertEqual(
                item["payload"]["lark_payload"],
                {"fields": ["素材方向", "状态"], "rows": [["方向 A", "待用"]]},
            )

    def test_retry_pending_removes_safe_success_and_keeps_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = self.make_fake_lark(
                tmp,
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    echo '{"data":{"record_id_list":["recXXX"]}}'
                    exit 0
                    """
                ),
            )
            env = self.make_env(tmp, fake)
            pending = self.pending_path(tmp)
            pending.parent.mkdir(parents=True)
            safe = {
                "schema_version": 1,
                "op_id": "safe-1",
                "op_type": "record_batch_update",
                "idempotency_key": "sha256:safe",
                "payload": {
                    "base_token": "app_token_test",
                    "table_id": "tblLWPSHrZT95oy7",
                    "lark_payload": {
                        "record_id_list": ["recXXX"],
                        "patch": {"状态": "已用"},
                    },
                },
                "retry_count": 0,
                "max_retries": 3,
                "retryable": True,
                "ambiguous": False,
                "last_error": "previous timeout",
                "created_at": "2026-05-17T20:30:00+08:00",
                "updated_at": "2026-05-17T20:30:00+08:00",
            }
            ambiguous = dict(safe)
            ambiguous.update(
                {
                    "op_id": "ambiguous-1",
                    "op_type": "record_batch_create",
                    "idempotency_key": "sha256:ambiguous",
                    "ambiguous": True,
                }
            )
            pending.write_text(
                json.dumps(safe, ensure_ascii=False)
                + "\n"
                + json.dumps(ambiguous, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )

            result = self.run_script("retry_pending.py", env=env)
            payload = self.read_json_stdout(result)

            self.assertEqual(payload["processed"], 2)
            self.assertEqual(payload["succeeded"], 1)
            self.assertEqual(payload["ambiguous_skipped"], 1)
            remaining = [
                json.loads(line)
                for line in pending.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual([item["op_id"] for item in remaining], ["ambiguous-1"])

    def test_write_image_group_dry_run_separates_record_fields_and_attachments(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.make_env(tmp)
            result = self.run_script(
                "write_image_group.py",
                "--direction-id",
                "recDir",
                "--copy-id",
                "recCopy",
                "--parent-group-id",
                "null",
                "--images",
                '[{"index":1,"path":"/tmp/set1_img1.png","prompt":"图1 prompt"},{"index":2,"path":"/tmp/set1_img2.png","prompt":"图2 prompt"}]',
                "--metadata",
                '{"渠道":"应用商店","图片形式":"双图","比例":"3:2","状态":"待用"}',
                "--dry-run",
                env=env,
            )
            payload = self.read_json_stdout(result)

            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["operation"], "image_group_create")
            self.assertEqual(
                payload["record_payload"]["fields"],
                ["关联方向", "关联文案", "渠道", "图片形式", "比例", "状态", "图1提示词", "图2提示词"],
            )
            self.assertEqual(
                payload["record_payload"]["rows"],
                [[["recDir"], ["recCopy"], "应用商店", "双图", "3:2", "待用", "图1 prompt", "图2 prompt"]],
            )
            self.assertEqual(
                payload["attachments"],
                [
                    {"field_id": "图1", "file": "/tmp/set1_img1.compressed-200kb.jpg", "name": "set1_img1.compressed-200kb.jpg"},
                    {"field_id": "图2", "file": "/tmp/set1_img2.compressed-200kb.jpg", "name": "set1_img2.compressed-200kb.jpg"},
                ],
            )
            self.assertEqual(
                payload["compression"],
                [
                    {"source": "/tmp/set1_img1.png", "output": "/tmp/set1_img1.compressed-200kb.jpg", "target_kb": 200},
                    {"source": "/tmp/set1_img2.png", "output": "/tmp/set1_img2.compressed-200kb.jpg", "target_kb": 200},
                ],
            )
            self.assertFalse(self.pending_path(tmp).exists())

    def test_write_image_group_dry_run_passes_target_dimensions_to_compression(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.make_env(tmp)
            result = self.run_script(
                "write_image_group.py",
                "--copy-id",
                "recCopy",
                "--images",
                '[{"index":1,"path":"/tmp/set1_img1.png","target_width":984,"target_height":422,"target_kb":200}]',
                "--metadata",
                '{"图片形式":"单图","版位":"华为 每日精选 内容封面","状态":"待用"}',
                "--dry-run",
                env=env,
            )
            payload = self.read_json_stdout(result)

            self.assertEqual(payload["compression"][0]["target_width"], 984)
            self.assertEqual(payload["compression"][0]["target_height"], 422)
            self.assertEqual(
                payload["attachments"],
                [{"field_id": "图1", "file": "/tmp/set1_img1.984x422.compressed-200kb.jpg", "name": "set1_img1.984x422.compressed-200kb.jpg"}],
            )

    def test_write_image_group_accepts_string_image_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.make_env(tmp)
            result = self.run_script(
                "write_image_group.py",
                "--copy-id",
                "recCopy",
                "--images",
                '["/tmp/set1_img1.png","/tmp/set1_img2.png"]',
                "--metadata",
                '{"图片形式":"双图","状态":"待用"}',
                "--dry-run",
                env=env,
            )
            payload = self.read_json_stdout(result)

            self.assertEqual(
                payload["record_payload"],
                {"fields": ["关联文案", "图片形式", "状态"], "rows": [[["recCopy"], "双图", "待用"]]},
            )
            self.assertEqual(
                payload["attachments"],
                [
                    {"field_id": "图1", "file": "/tmp/set1_img1.compressed-200kb.jpg", "name": "set1_img1.compressed-200kb.jpg"},
                    {"field_id": "图2", "file": "/tmp/set1_img2.compressed-200kb.jpg", "name": "set1_img2.compressed-200kb.jpg"},
                ],
            )
            self.assertFalse(self.pending_path(tmp).exists())

    def test_write_image_group_uses_metadata_target_kb_without_writing_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.make_env(tmp)
            result = self.run_script(
                "write_image_group.py",
                "--copy-id",
                "recCopy",
                "--images",
                '["/tmp/set1_img1.png"]',
                "--metadata",
                '{"图片形式":"单图","目标KB":150,"状态":"待用"}',
                "--dry-run",
                env=env,
            )
            payload = self.read_json_stdout(result)

            self.assertEqual(
                payload["record_payload"],
                {"fields": ["关联文案", "图片形式", "状态"], "rows": [[["recCopy"], "单图", "待用"]]},
            )
            self.assertEqual(
                payload["attachments"],
                [{"field_id": "图1", "file": "/tmp/set1_img1.compressed-150kb.jpg", "name": "set1_img1.compressed-150kb.jpg"}],
            )
            self.assertEqual(payload["compression"][0]["target_kb"], 150)
            self.assertFalse(self.pending_path(tmp).exists())

    def test_write_image_group_can_skip_compression_for_debugging(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.make_env(tmp)
            result = self.run_script(
                "write_image_group.py",
                "--copy-id",
                "recCopy",
                "--images",
                '["/tmp/set1_img1.png"]',
                "--metadata",
                '{"图片形式":"单图","状态":"待用"}',
                "--no-compress",
                "--dry-run",
                env=env,
            )
            payload = self.read_json_stdout(result)

            self.assertEqual(
                payload["attachments"],
                [{"field_id": "图1", "file": "/tmp/set1_img1.png", "name": "set1_img1.png"}],
            )
            self.assertEqual(payload["compression"], [])
            self.assertFalse(self.pending_path(tmp).exists())

    def test_write_image_group_rejects_system_managed_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.make_env(tmp)
            result = self.run_script(
                "write_image_group.py",
                "--copy-id",
                "recCopy",
                "--images",
                '["/tmp/set1_img1.png"]',
                "--metadata",
                '{"图片形式":"单图","创建时间":"2026-05-17 21:00","状态":"待用"}',
                "--dry-run",
                env=env,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("system-managed", result.stderr)
            self.assertFalse(self.pending_path(tmp).exists())


if __name__ == "__main__":
    unittest.main()
