from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BATCH_SCRIPT = PLUGIN_ROOT / "skills" / "onion-image" / "scripts" / "batch_render.py"


FAKE_RENDER = """\
#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--prompt", required=True)
parser.add_argument("--size")
parser.add_argument("--quality")
parser.add_argument("--output", required=True)
parser.add_argument("--reference", action="append", default=[])
args, _ = parser.parse_known_args()

log_path = Path(os.environ["FAKE_RENDER_LOG"])
state_dir = Path(os.environ["FAKE_RENDER_STATE"])
state_dir.mkdir(parents=True, exist_ok=True)
job_id = "unknown"
for part in args.prompt.split():
    if part.startswith("JOB="):
        job_id = part.split("=", 1)[1]
        break

def log(event):
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"event": event, "job_id": job_id, "t": time.time()}, ensure_ascii=False) + "\\n")

log("start")
time.sleep(float(os.environ.get("FAKE_RENDER_SLEEP", "0.06")))
if "RATE_LIMIT_ONCE" in args.prompt:
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


def run_batch(root: Path, manifest: dict, *, concurrency: int | None = 6, fallback: int | None = 3) -> tuple[dict, list[dict]]:
    manifest_path = root / "manifest.json"
    result_path = root / "image-render-result.json"
    log_path = root / "render.log"
    state_dir = root / "state"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
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
