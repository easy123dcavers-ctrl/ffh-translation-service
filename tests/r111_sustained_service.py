"""R111: longer-form, repeated-batch, restart and live-health stress test.
Runs ONLY inside isolated 512MiB Docker container without network. Invented text.
This is a resource-reliability check, NOT translation quality certification.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

PORT = 18741
ROOT_URL = f"http://127.0.0.1:{PORT}"
OUT = Path("r111-output")
MiB = 1024 * 1024
LIMIT_BYTES = 512 * MiB
NUMBERS = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?")


def read_cgroup(name):
    path = Path("/sys/fs/cgroup") / name
    if not path.is_file():
        raise RuntimeError(f"Missing required cgroup metric {name}")
    data = path.read_text().strip()
    if not data.isdigit():
        raise RuntimeError(f"Non-numeric cgroup metric {name}={data}")
    return int(data)


def memory_events():
    path = Path("/sys/fs/cgroup/memory.events")
    items = {}
    for row in path.read_text().splitlines():
        k, v = row.split()
        items[k] = int(v)
    return items


def http(path, payload=None, timeout=15):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        ROOT_URL + path, data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, json.loads(res.read()), round(time.monotonic()-start, 3)
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read()), round(time.monotonic()-start, 3)


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def measure_numeric_change(source, target):
    src = sorted(NUMBERS.findall(source))
    translated = sorted(NUMBERS.findall(target))
    return src != translated


def run_round(round_id):
    logfile = OUT / f"gunicorn-round-{round_id}.log"
    env = dict(os.environ)
    env.update({
        "ARGOS_CHUNK_TYPE": "MINISBD",
        "ARGOS_COMPUTE_TYPE": "int8",
        "FFH_TRANSLATION_CACHE_ENABLED": "false",
        "FFH_TARGET_LANGUAGE": "es",
        "FFH_MULTILINGUAL": "false",
        "OMP_NUM_THREADS": "1",
    })
    round_report = {
        "round": round_id, "batch_requests": 0,
        "translated_batch_items": 0, "long_text_requests": 0,
        "peak_batch_health_seconds": 0, "numeric_mismatch_count": 0,
        "startup_seconds": None, "engine_error_count": 0,
        "batch_wall_seconds": [],
    }
    with logfile.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", "gunicorn", "--workers", "1", "--threads", "2",
             "--timeout", "120", "--bind", f"127.0.0.1:{PORT}", "app:app"],
            env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        round_report["server_pid"] = proc.pid
        try:
            begun = time.monotonic()
            while time.monotonic() - begun < 35:
                expect(proc.poll() is None, "Gunicorn exited before health ready")
                try:
                    status, data, _ = http("/health", timeout=1)
                    if status == 200 and data.get("status") == "ok":
                        break
                except (OSError, ValueError):
                    time.sleep(0.15)
            else:
                raise RuntimeError("Gunicorn health not ready after 35 seconds")
            round_report["startup_seconds"] = round(time.monotonic() - begun, 3)

            info_code, info, _ = http("/")
            expect(info_code == 200 and info.get("max_batch_items") == 25,
                   "Unexpected HTTP API batch limit")
            for batch_id in range(2):
                items = []
                for index in range(25):
                    n = round_id * 100 + batch_id * 25 + index + 1
                    src = (f"Mock notebook card {n} is on the library shelf. "
                           f"The card contains {n+17} fictional examples.")
                    items.append({"id": str(n), "q": src})
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    pending = pool.submit(http, "/translate-batch", {
                        "source": "en", "target": "es", "items": items
                    }, 110)
                    time.sleep(0.07)
                    expect(not pending.done(),
                           "Translation batch finished before health-under-load probe")
                    code, health, health_seconds = http("/health", timeout=5)
                    expect(code == 200 and health.get("status") == "ok",
                           "Health failed while 25-item batch was active")
                    expect(health_seconds < 5, "Health timed out during batch")
                    status, reply, seconds = pending.result(timeout=115)
                expect(status == 200 and reply.get("count") == 25,
                       "25-item batch rejected")
                answers = reply.get("results", [])
                expect(len(answers) == 25 and all(v.get("ok") for v in answers),
                       "One or more Argos batch items failed")
                expect([v["id"] for v in answers] ==
                       [v["id"] for v in items], "Batch IDs or order changed")
                for original, translated in zip(items, answers):
                    draft = translated.get("translatedText")
                    expect(isinstance(draft, str) and bool(draft.strip()),
                           "Empty translated candidate")
                    round_report["numeric_mismatch_count"] += int(
                        measure_numeric_change(original["q"], draft))
                round_report["batch_requests"] += 1
                round_report["translated_batch_items"] += 25
                round_report["peak_batch_health_seconds"] = max(
                    round_report["peak_batch_health_seconds"], health_seconds)
                round_report["batch_wall_seconds"].append(seconds)

            # Bounded long, multi-paragraph input: invented non-safety examples only.
            paragraphs = [
                "The imaginary library contains a small blue notebook. "
                "Its pages describe ordinary household objects and fictional records. "
                "A curator writes one short note beside each numbered card.",
                "The next page describes a classroom with tables, chairs, and books. "
                "A teacher reads aloud while the students check the dates on the labels. "
                "This is an invented translation example with no food safety instructions.",
                "In the evening the librarian closes the door. "
                "Tomorrow the notebook will return to the shelf near the window."
            ]
            for case in range(3):
                text = "\n\n".join(paragraphs[case:] + paragraphs[:case])
                text = f"Imaginary example {round_id+1} entry {case+1}.\n\n" + text
                expect(400 <= len(text) <= 1400, "Long fixture outside safe bounds")
                status, data, seconds = http("/translate", {
                    "q": text, "source": "en", "target": "es"
                }, timeout=110)
                expect(status == 200, f"Long translation HTTP error {status}")
                draft = data.get("translatedText")
                expect(isinstance(draft, str) and len(draft.strip()) > 100,
                       "Long translation output unexpectedly small")
                round_report["long_text_requests"] += 1
                round_report["numeric_mismatch_count"] += int(
                    measure_numeric_change(text, draft))
                round_report.setdefault("long_text_seconds", []).append(seconds)

            expect(http("/health")[0] == 200, "Health failed after prolonged work")
            expect(http("/translate", ["not an object"])[0] == 400,
                   "Invalid request unexpectedly accepted")
            expect(http("/translate-batch", {
                "source":"en","target":"es","items":["invented"]*26})[0] == 400,
                   "Oversized batch unexpectedly accepted")
            return round_report
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            round_report["server_exit_status"] = proc.returncode


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    expect(read_cgroup("memory.max") == LIMIT_BYTES,
           "STOP: This test requires a real enforced 512MiB cgroup")
    before = memory_events()
    result = {
        "test": "R111-512MiB-Gunicorn-repeat-and-restart",
        "production_writes": 0, "netlify_deploys": 0,
        "only_synthetic_data": True, "runtime_network": "disabled",
        "translation_quality_human_approved": False,
        "model_build": "experimental pinned Argos 1.11.0+ffhlite1",
        "rounds": [], "cgroup_limit_mib": 512,
        "request_cache_enabled": False,
    }
    started = time.monotonic()
    try:
        for i in range(2):
            round_result = run_round(i)
            result["rounds"].append(round_result)
            print("R111_ROUND", json.dumps(round_result, sort_keys=True), flush=True)
        expect(result["rounds"][0]["server_pid"] !=
               result["rounds"][1]["server_pid"], "Server restart not observed")
        expect(sum(x["translated_batch_items"] for x in result["rounds"]) == 100,
               "Expected exactly 100 successful batch translations")
        expect(sum(x["long_text_requests"] for x in result["rounds"]) == 6,
               "Expected exactly six long multi-paragraph translations")
    finally:
        peak = read_cgroup("memory.peak")
        after = memory_events()
        result["peak_cgroup_mib"] = round(peak / MiB, 2)
        result["headroom_pct"] = round((LIMIT_BYTES - peak) / LIMIT_BYTES * 100, 2)
        result["memory_events_delta"] = {
            key: after.get(key, 0) - before.get(key, 0) for key in after
        }
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        (OUT / "r111-summary.json").write_text(
            json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        print("R111_SUMMARY", json.dumps({
            key: val for key, val in result.items() if key != "rounds"
        }, sort_keys=True), flush=True)
    expect(result["headroom_pct"] >= 15, "Memory headroom below 15%")
    expect(result["memory_events_delta"].get("oom_kill", 0) == 0,
           "Memory limit OOM kill occurred")
    # Candidate numerical changes are reported, not silently approved.
    print("R111_FINISHED", json.dumps({
        "rounds": len(result["rounds"]),
        "batch_items": sum(x["translated_batch_items"] for x in result["rounds"]),
        "long_requests": sum(x["long_text_requests"] for x in result["rounds"]),
        "numeric_mismatch_candidates": sum(
            x["numeric_mismatch_count"] for x in result["rounds"]),
        "memory_headroom_pct": result["headroom_pct"],
        "release_ready": False,
    }), flush=True)


if __name__ == "__main__":
    main()
