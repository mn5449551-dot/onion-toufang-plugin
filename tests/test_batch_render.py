from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BATCH_SCRIPT = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "batch_render.py"


def load_batch_module():
    spec = importlib.util.spec_from_file_location("onion_batch_render", BATCH_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FAKE_RENDER = """\
#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--input-json")
parser.add_argument("--prompt")
parser.add_argument("--size")
parser.add_argument("--quality")
parser.add_argument("--output", required=True)
parser.add_argument("--reference", action="append", default=[])
args, _ = parser.parse_known_args()

payload = {}
if args.input_json:
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
prompt = str(payload.get("prompt") or args.prompt or "")
references = payload.get("reference_images") or args.reference

log_path = Path(os.environ["FAKE_RENDER_LOG"])
state_dir = Path(os.environ["FAKE_RENDER_STATE"])
state_dir.mkdir(parents=True, exist_ok=True)
job_id = "unknown"
for part in prompt.split():
    if part.startswith("JOB="):
        job_id = part.split("=", 1)[1]
        break

def log(event):
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": event, "job_id": job_id, "t": time.time(), "references": references}, ensure_ascii=False) + "\\n")

log("start")
time.sleep(float(os.environ.get("FAKE_RENDER_SLEEP", "0.06")))
if "RATE_LIMIT_ONCE" in prompt:
    marker = state_dir / f"{job_id}.rate-limit-once"
    if not marker.exists():
        marker.write_text("failed", encoding="utf-8")
        log("fail")
        print("HTTP 429: rate limit", file=sys.stderr)
        raise SystemExit(3)

output = Path(args.output)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(b"fake-png")
log("end")
print(json.dumps({"valid": True, "filepath": str(output)}, ensure_ascii=False))
"""


def write_fake_render(root: Path) -> Path:
    script = root / "fake_render.py"
    script.write_text(textwrap.dedent(FAKE_RENDER), encoding="utf-8")
    script.chmod(0o755)
    return script


def run_batch(
    root: Path,
    manifest: dict,
    *,
    config: dict | None = None,
    include_config_arg: bool = True,
    concurrency: int | None = 6,
    fallback: int | None = 3,
) -> tuple[dict, list[dict]]:
    manifest_path = root / "manifest.json"
    config_path = root / "image-config-result.json"
    result_path = root / "image-render-result.json"
    log_path = root / "render.log"
    state_dir = root / "state"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    config_path.write_text(
        json.dumps(
            config
            or {
                "request_id": manifest.get("request_id"),
                "logo": "不用",
                "logo_asset_id": "",
                "logo_reference_path": "",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    fake_render = write_fake_render(root)
    command = [
        sys.executable,
        str(BATCH_SCRIPT),
        "--manifest",
        str(manifest_path),
        "--output",
        str(result_path),
        "--render-script",
        str(fake_render),
    ]
    if include_config_arg:
        command.extend(["--config", str(config_path)])
    if concurrency is not None:
        command.extend(["--concurrency", str(concurrency)])
    if fallback is not None:
        command.extend(["--fallback-concurrency", str(fallback)])
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            **os_environ_without_openai(),
            "FAKE_RENDER_LOG": str(log_path),
            "FAKE_RENDER_STATE": str(state_dir),
            "FAKE_RENDER_SLEEP": "0.06",
        },
        check=True,
    )
    payload = json.loads(result.stdout)
    events = []
    if log_path.exists():
        events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return payload, events


def os_environ_without_openai() -> dict[str, str]:
    import os

    env = os.environ.copy()
    env.pop("LAOZHANG_API_KEY", None)
    return env


def simple_job(root: Path, set_no: int, slot: int = 1, **extra) -> dict:
    job_id = f"set{set_no}-img{slot}"
    job = {
        "job_id": job_id,
        "set_id": f"set{set_no}",
        "slot": slot,
        "image_form": "single",
        "prompt": f"JOB={job_id}",
        "size": "1024x1024",
        "quality": "low",
        "output": str(root / "renders" / f"{job_id}.png"),
        "references": [],
        "depends_on": [],
    }
    job.update(extra)
    return job


def max_active(events: list[dict]) -> int:
    timeline = sorted(
        [(event["t"], 1 if event["event"] == "start" else -1) for event in events if event["event"] in {"start", "end", "fail"}],
        key=lambda item: (item[0], -item[1]),
    )
    active = 0
    peak = 0
    for _, delta in timeline:
        active += delta
        peak = max(peak, active)
    return peak


class BatchRenderTests(unittest.TestCase):
    def test_batch_render_discovers_sibling_config_when_flag_is_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {"request_id": "req-auto-config", "jobs": [simple_job(root, 1)]}

            payload, _ = run_batch(root, manifest, include_config_arg=False)

        self.assertEqual(payload["status"], "completed")

    def test_render_input_defaults_to_high_quality(self):
        batch = load_batch_module()
        with tempfile.TemporaryDirectory() as tmp:
            job = simple_job(Path(tmp), 1)
            job.pop("quality")

            input_path = batch.write_render_input(job)
            payload = json.loads(input_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["quality"], "high")

    def test_structured_logo_reference_is_preserved_in_render_input_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt = (
                "JOB=set1-img1 参考图说明：参考图1 是品牌 Logo。"
                "左上角原样呈现参考图1的完整 Logo，图形、文字、颜色、比例、轮廓及角标均与原图一致，"
                "不得重绘、变形、简化或拆分；Logo直接融入画面原有背景，周围延续整体色调，"
                "不另加底板、色块、边框或弧形区域，仅调整整体大小和位置。"
            )
            logo = {
                "label": "参考图1",
                "role": "品牌 Logo 和 APP 标识参考图",
                "asset_id": "logo.onion.app.001",
                "path": "assets/logos/onion-logo-app-001.png",
            }
            manifest = {
                "request_id": "req-logo",
                "jobs": [simple_job(root, 1, prompt=prompt, references=[logo])],
            }
            config = {
                "request_id": "req-logo",
                "logo": "洋葱学园+APP",
                "logo_asset_id": "logo.onion.app.001",
                "logo_reference_path": "assets/logos/onion-logo-app-001.png",
            }

            payload, events = run_batch(root, manifest, config=config)

            self.assertEqual(payload["status"], "completed")
            start = next(event for event in events if event["event"] == "start")
            self.assertEqual(start["references"], [logo])

    def test_selected_logo_must_match_every_single_or_base_job_but_not_branch_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt = (
                "JOB=set1-img1 参考图说明：参考图1 是品牌 Logo。"
                "左上角原样呈现参考图1的完整 Logo，图形、文字、颜色、比例、轮廓及角标均与原图一致，"
                "不得重绘、变形、简化或拆分；Logo直接融入画面原有背景，周围延续整体色调，"
                "不另加底板、色块、边框或弧形区域，仅调整整体大小和位置。"
            )
            wrong_logo = {
                "label": "参考图1",
                "role": "品牌 Logo 参考图",
                "asset_id": "logo.onion.standard.001",
                "path": "assets/logos/onion-logo-standard-001.png",
            }
            manifest = {
                "request_id": "req-logo-mismatch",
                "jobs": [simple_job(root, 1, prompt=prompt, references=[wrong_logo])],
            }
            config = {
                "request_id": "req-logo-mismatch",
                "logo": "洋葱学园+APP",
                "logo_asset_id": "logo.onion.app.001",
                "logo_reference_path": "assets/logos/onion-logo-app-001.png",
            }

            with self.assertRaises(subprocess.CalledProcessError) as raised:
                run_batch(root, manifest, config=config)

            self.assertIn("Logo", raised.exception.stderr)

    def test_single_image_jobs_run_with_configured_concurrency(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {"request_id": "req-batch", "jobs": [simple_job(root, i) for i in range(1, 9)]}

            payload, events = run_batch(root, manifest, concurrency=6)

            self.assertEqual(payload["status"], "completed")
            self.assertFalse(payload["fallback_used"])
            self.assertLessEqual(max_active(events), 6)
            self.assertGreater(max_active(events), 1)
            self.assertEqual(len(payload["sets"]), 8)

    def test_manifest_can_define_concurrency_when_cli_omits_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "request_id": "req-manifest-concurrency",
                "concurrency": 2,
                "fallback_concurrency": 1,
                "jobs": [simple_job(root, i) for i in range(1, 5)],
            }

            payload, events = run_batch(root, manifest, concurrency=None, fallback=None)

            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["concurrency_used"], 2)
            self.assertEqual(payload["fallback_concurrency"], 1)
            self.assertLessEqual(max_active(events), 2)
            self.assertGreater(max_active(events), 1)

    def test_double_and_triple_jobs_wait_for_same_set_base_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "request_id": "req-chain",
                "jobs": [
                    simple_job(root, 1, 1, image_form="double"),
                    simple_job(root, 1, 2, image_form="double", depends_on=["set1-img1"]),
                    simple_job(root, 2, 1, image_form="triple"),
                    simple_job(root, 2, 2, image_form="triple", depends_on=["set2-img1"]),
                    simple_job(root, 2, 3, image_form="triple", depends_on=["set2-img1"]),
                ],
            }

            payload, events = run_batch(root, manifest, concurrency=6)

            self.assertEqual(payload["status"], "completed")
            by_job = {}
            for event in events:
                by_job.setdefault(event["job_id"], {})[event["event"]] = event["t"]
            self.assertGreaterEqual(by_job["set1-img2"]["start"], by_job["set1-img1"]["end"])
            self.assertGreaterEqual(by_job["set2-img2"]["start"], by_job["set2-img1"]["end"])
            self.assertGreaterEqual(by_job["set2-img3"]["start"], by_job["set2-img1"]["end"])

    def test_existing_outputs_are_skipped_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "renders" / "set1-img1.png"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"already-rendered")
            manifest = {"request_id": "req-resume", "jobs": [simple_job(root, 1), simple_job(root, 2)]}

            payload, events = run_batch(root, manifest, concurrency=6)

            self.assertEqual(payload["status"], "completed")
            self.assertEqual([event["job_id"] for event in events if event["event"] == "start"], ["set2-img1"])
            set1 = next(item for item in payload["sets"] if item["set_id"] == "set1")
            self.assertEqual(set1["status"], "completed")

    def test_retryable_rate_limit_downgrades_to_fallback_concurrency_and_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job = simple_job(root, 1, prompt="JOB=set1-img1 RATE_LIMIT_ONCE")
            manifest = {"request_id": "req-rate", "jobs": [job, simple_job(root, 2), simple_job(root, 3), simple_job(root, 4)]}

            payload, events = run_batch(root, manifest, concurrency=6, fallback=3)

            self.assertEqual(payload["status"], "completed")
            self.assertTrue(payload["fallback_used"])
            self.assertEqual(payload["fallback_concurrency"], 3)
            starts = [event for event in events if event["event"] == "start" and event["job_id"] == "set1-img1"]
            self.assertEqual(len(starts), 2)
            self.assertEqual(payload["failed_jobs"], [])


if __name__ == "__main__":
    unittest.main()
