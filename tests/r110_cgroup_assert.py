"""R110 disposable cgroup-limited Gunicorn integration validator.

Intended to run ONLY in a docker container with --memory=512m and --memory-swap=512m,
network disabled, one worker and two threads. No production API or FFH private data.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


RESULT_DIR = Path("r106-output")
MB = 1024 * 1024
EXPECTED_LIMIT = 512 * MB
HEADROOM_PCT_REQUIRED = 15


def cgroup_stat(name: str):
    file = Path("/sys/fs/cgroup") / name
    if not file.is_file():
        raise RuntimeError(f"cgroup v2 metric missing: {name}")
    value = file.read_text().strip()
    if not value.isdigit():
        raise RuntimeError(f"Non-numeric cgroup limit: {name}={value}")
    return int(value)


def main():
    RESULT_DIR.mkdir(exist_ok=True, parents=True)
    limit = cgroup_stat("memory.max")
    if limit != EXPECTED_LIMIT:
        raise RuntimeError(
            f"STOP: expected Docker-enforced 512 MiB cap, observed {limit}"
        )
    started = time.monotonic()
    outcome = subprocess.run(
        [sys.executable, "tests/r106_localhost_service.py"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=180,
    )
    print(outcome.stdout[-12000:], flush=True)
    peak = cgroup_stat("memory.peak")
    usage = cgroup_stat("memory.current")
    events_file = Path("/sys/fs/cgroup/memory.events")
    events = {}
    for line in events_file.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            events[parts[0]] = int(parts[1])
    report_path = RESULT_DIR / "r106-summary.json"
    service_report = json.loads(report_path.read_text()) if report_path.exists() else {}
    headroom = (limit - peak) / limit * 100
    summary = {
        "test": "R110-isolated-Docker-cgroup-Gunicorn-two-threads",
        "memory_limit_mib": round(limit / MB, 2),
        "cgroup_peak_mib": round(peak / MB, 2),
        "memory_current_mib": round(usage / MB, 2),
        "memory_headroom_pct": round(headroom, 2),
        "headroom_threshold_pct": HEADROOM_PCT_REQUIRED,
        "memory_events": events,
        "service_test_exit_code": outcome.returncode,
        "service_success": outcome.returncode == 0,
        "batch_active_at_health_probe": service_report.get(
            "batch_active_at_health_probe"
        ),
        "health_during_batch": service_report.get("results", {}).get(
            "health_during_batch", [None])[0],
        "all_25_batch_entries_ok": all(
            row.get("ok") for row in
            service_report.get("results", {}).get("batch", [None, {}])[1].get(
                "results", []
            )
        ),
        "wall_seconds": round(time.monotonic() - started, 2),
        "network_disabled_at_runtime": True,
        "experimental_argos_build": True,
        "production_writes": 0,
        "netlify_deployments": 0,
        "only_synthetic_data": True,
    }
    (RESULT_DIR / "r110-cgroup-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("R110_CGROUP_SUMMARY", json.dumps(summary, sort_keys=True), flush=True)

    if outcome.returncode != 0:
        raise RuntimeError("Gunicorn smoke did not pass")
    if events.get("oom_kill", 0) > 0:
        raise RuntimeError("512 MiB container encountered an OOM kill")
    if not summary["batch_active_at_health_probe"]:
        raise RuntimeError("Health was not checked during an active translation batch")
    if summary["health_during_batch"] != 200:
        raise RuntimeError("Health failed during active translation")
    if not summary["all_25_batch_entries_ok"]:
        raise RuntimeError("Translation batch failed")
    if headroom < HEADROOM_PCT_REQUIRED:
        raise RuntimeError("Insufficient memory headroom for candidate release")


if __name__ == "__main__":
    main()
