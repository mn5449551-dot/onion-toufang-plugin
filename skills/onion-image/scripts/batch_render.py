#!/usr/bin/env python3
"""
Run multiple onion image render jobs with bounded local concurrency.

This script does not call the image API directly. It shells out to render.py for
each job so API compatibility, reference-image handling, size fallback, and
error classification stay in one place.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RENDER_SCRIPT = SCRIPT_DIR / "render.py"
DEFAULT_CONCURRENCY = 12
DEFAULT_FALLBACK_CONCURRENCY = 3
PROVIDER = "laozhang-gpt-image-2-enterprise"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from logo_reference import validate_manifest_logo  # noqa: E402


def clean_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def local_concurrency(manifest: dict[str, Any], cli_value: int | None, env_name: str, default: int) -> int:
    if cli_value is not None:
        return clean_int(cli_value, default)
    manifest_keys = {
        "ONION_IMAGE_CONCURRENCY": ("concurrency", "onion_image_concurrency"),
        "ONION_IMAGE_FALLBACK_CONCURRENCY": ("fallback_concurrency", "onion_image_fallback_concurrency"),
    }.get(env_name, (env_name.lower(),))
    for key in manifest_keys:
        if manifest.get(key) is not None:
            return clean_int(manifest.get(key), default)
    return clean_int(os.environ.get(env_name), default)


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest must be a JSON object")
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("manifest.jobs must be a non-empty list")
    seen: set[str] = set()
    for index, job in enumerate(jobs, start=1):
        if not isinstance(job, dict):
            raise ValueError(f"job {index} must be an object")
        job_id = str(job.get("job_id") or "").strip()
        if not job_id:
            raise ValueError(f"job {index} missing job_id")
        if job_id in seen:
            raise ValueError(f"duplicate job_id: {job_id}")
        seen.add(job_id)
        if not str(job.get("set_id") or "").strip():
            raise ValueError(f"{job_id} missing set_id")
        if not str(job.get("prompt") or "").strip():
            raise ValueError(f"{job_id} missing prompt")
        if not str(job.get("output") or "").strip():
            raise ValueError(f"{job_id} missing output")
        for dep in job.get("depends_on") or []:
            if str(dep) not in seen and not any(str(other.get("job_id")) == str(dep) for other in jobs if isinstance(other, dict)):
                raise ValueError(f"{job_id} depends on unknown job {dep}")
    return data


def existing_output(job: dict[str, Any]) -> bool:
    path = Path(str(job.get("output"))).expanduser()
    return path.is_file() and path.stat().st_size > 0


def render_input_path(job: dict[str, Any]) -> Path:
    output = Path(str(job["output"])).expanduser()
    return output.with_suffix(".render-input.json")


def write_render_input(job: dict[str, Any]) -> Path:
    payload = {
        "prompt": str(job["prompt"]),
        "quality": str(job.get("quality") or "high"),
        "reference_images": job.get("references") or job.get("reference_images") or [],
    }
    if job.get("size"):
        payload["size"] = str(job["size"])
    elif job.get("aspect_ratio"):
        payload["aspect_ratio"] = str(job["aspect_ratio"])
    path = render_input_path(job)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def render_command(render_script: Path, job: dict[str, Any]) -> list[str]:
    input_path = write_render_input(job)
    return [
        sys.executable,
        str(render_script),
        "--input-json",
        str(input_path),
        "--output",
        str(job["output"]),
    ]


def is_retryable_failure(returncode: int, stdout: str, stderr: str) -> bool:
    text = f"{stdout}\n{stderr}".lower()
    markers = ("429", "rate limit", "timeout", "temporarily", "server error", " 5", "5xx")
    return returncode == 3 or any(marker in text for marker in markers)


def run_one(render_script: Path, job: dict[str, Any]) -> dict[str, Any]:
    result = subprocess.run(render_command(render_script, job), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ok = result.returncode == 0 and existing_output(job)
    return {
        "job_id": str(job["job_id"]),
        "set_id": str(job["set_id"]),
        "slot": int(job.get("slot") or 1),
        "output": str(Path(str(job["output"])).expanduser().resolve()),
        "ok": ok,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "retryable": is_retryable_failure(result.returncode, result.stdout, result.stderr),
    }


def run_jobs(render_script: Path, jobs: list[dict[str, Any]], concurrency: int) -> list[dict[str, Any]]:
    if not jobs:
        return []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        futures = {executor.submit(run_one, render_script, job): job for job in jobs}
        return [future.result() for future in as_completed(futures)]


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def set_results(jobs: list[dict[str, Any]], job_status: dict[str, str]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        grouped.setdefault(str(job["set_id"]), []).append(job)

    sets = []
    for set_id in sorted(grouped):
        group = sorted(grouped[set_id], key=lambda item: int(item.get("slot") or 1))
        completed = all(job_status.get(str(job["job_id"])) in {"completed", "skipped"} for job in group)
        sets.append(
            {
                "set_id": set_id,
                "status": "completed" if completed else "failed",
                "images": [str(Path(str(job["output"])).expanduser().resolve()) for job in group if job_status.get(str(job["job_id"])) in {"completed", "skipped"}],
            }
        )
    return sets


def execute_manifest(manifest: dict[str, Any], render_script: Path, concurrency: int, fallback_concurrency: int) -> dict[str, Any]:
    request_id = str(manifest.get("request_id") or "unknown-request")
    jobs = list(manifest["jobs"])
    by_id = {str(job["job_id"]): job for job in jobs}
    job_status: dict[str, str] = {}
    attempts: dict[str, int] = {job_id: 0 for job_id in by_id}
    failed_jobs: list[dict[str, Any]] = []
    fallback_used = False

    for job_id, job in by_id.items():
        if existing_output(job):
            job_status[job_id] = "skipped"

    while True:
        pending = [job for job in jobs if str(job["job_id"]) not in job_status]
        if not pending:
            break
        ready = [
            job
            for job in pending
            if all(job_status.get(str(dep)) in {"completed", "skipped"} for dep in job.get("depends_on") or [])
        ]
        if not ready:
            for job in pending:
                job_id = str(job["job_id"])
                job_status[job_id] = "failed"
                failed_jobs.append({"job_id": job_id, "set_id": job.get("set_id"), "error": "dependencies_failed_or_cyclic"})
            break

        results = run_jobs(render_script, ready, concurrency)
        retryable_jobs = []
        for result in results:
            job_id = result["job_id"]
            attempts[job_id] += 1
            if result["ok"]:
                job_status[job_id] = "completed"
            elif result["retryable"] and attempts[job_id] == 1:
                retryable_jobs.append(by_id[job_id])
            else:
                job_status[job_id] = "failed"
                failed_jobs.append(
                    {
                        "job_id": job_id,
                        "set_id": result.get("set_id"),
                        "returncode": result.get("returncode"),
                        "stderr": result.get("stderr"),
                    }
                )

        if retryable_jobs:
            fallback_used = True
            retry_results = run_jobs(render_script, retryable_jobs, fallback_concurrency)
            for result in retry_results:
                job_id = result["job_id"]
                attempts[job_id] += 1
                if result["ok"]:
                    job_status[job_id] = "completed"
                else:
                    job_status[job_id] = "failed"
                    failed_jobs.append(
                        {
                            "job_id": job_id,
                            "set_id": result.get("set_id"),
                            "returncode": result.get("returncode"),
                            "stderr": result.get("stderr"),
                        }
                    )

    sets = set_results(jobs, job_status)
    failed_set_ids = sorted({item["set_id"] for item in sets if item["status"] != "completed"})
    if not failed_set_ids:
        status = "completed"
    elif len(failed_set_ids) < len(sets):
        status = "partial_failed"
    else:
        status = "failed"

    return {
        "request_id": request_id,
        "status": status,
        "provider": PROVIDER,
        "concurrency_used": concurrency,
        "fallback_concurrency": fallback_concurrency,
        "fallback_used": fallback_used,
        "sets": sets,
        "failed_jobs": failed_jobs,
        "failed_sets": failed_set_ids,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch render onion image jobs with bounded concurrency.")
    parser.add_argument("--manifest", required=True, help="JSON manifest with request_id and jobs.")
    parser.add_argument(
        "--config",
        help=(
            "Saved image-config-result.json for Logo and placement validation; "
            "defaults to image-config-result.json beside the manifest."
        ),
    )
    parser.add_argument("--output", help="Defaults to image-render-result.json beside manifest.")
    parser.add_argument("--render-script", default=str(DEFAULT_RENDER_SCRIPT), help=argparse.SUPPRESS)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--fallback-concurrency", type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest_path = Path(args.manifest).expanduser().resolve()
        manifest = load_manifest(manifest_path)
        config_path = (
            Path(args.config).expanduser().resolve()
            if args.config
            else manifest_path.parent / "image-config-result.json"
        )
        if not config_path.is_file():
            raise ValueError(
                f"config file not found: {config_path}. Pass --config or place "
                "image-config-result.json beside the manifest."
            )
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("config must be a JSON object")
        validate_manifest_logo(manifest, config)
        concurrency = local_concurrency(manifest, args.concurrency, "ONION_IMAGE_CONCURRENCY", DEFAULT_CONCURRENCY)
        fallback = local_concurrency(manifest, args.fallback_concurrency, "ONION_IMAGE_FALLBACK_CONCURRENCY", DEFAULT_FALLBACK_CONCURRENCY)
        result_path = Path(args.output).expanduser().resolve() if args.output else manifest_path.parent / "image-render-result.json"
        payload = execute_manifest(manifest, Path(args.render_script).expanduser().resolve(), concurrency, fallback)
        atomic_write_json(result_path, payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if payload["status"] in {"completed", "partial_failed"} else 3
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
