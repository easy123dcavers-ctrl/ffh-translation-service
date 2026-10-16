"""R103 isolated Argos memory profiles. Invented English inputs only; no FFH access."""
import argparse
import json
import os
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

SENTENCES = [
    "The red notebook is on the table.",
    "There are 4 empty jars on the shelf.",
    "Write the date on the clean label.",
    "Sample 12 is a test record.",
    "These words are fictional.",
    "A wooden spoon is beside the bowl.",
    "Page 7 includes the list of examples.",
    "The small kitchen has a blue door.",
    "First open the notebook. Then turn to page 3.",
    "The children are reading. The teacher is writing.",
    "We are measuring 15 g of salt for this demonstration.",
    "Use 20 mL of water for the mock experiment.",
    "There are 10 numbered cards in this box.",
    "Look at chart 6 before continuing.",
    "The book belongs to the local library.",
    "This is only a software performance test.",
    "Read the short sentence aloud.",
    "The cup is half full of cold water.",
    "The afternoon meeting begins at 2.",
    "Our sample is not intended as food guidance.",
]
NUMBERS = re.compile(r"(?<![a-zA-Z])\d+(?:[.,]\d+)?")

def get_peak_mb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)

def child(profile, worker):
    # All model settings supplied in env before importing argostranslate.
    from argostranslate import settings, translate
    start_imported = time.perf_counter()
    results = []
    for source in SENTENCES:
        results.append(translate.translate(source, "en", "es"))
    seconds = round(time.perf_counter() - start_imported, 3)
    flagged = []
    for i, (src, dst) in enumerate(zip(SENTENCES, results)):
        problems = []
        if not dst or dst.strip() == src.strip():
            problems.append("empty_or_unchanged")
        if sorted(NUMBERS.findall(src)) != sorted(NUMBERS.findall(dst)):
            problems.append("numbers_differ")
        if problems:
            flagged.append({"index": i, "problems": problems})
    summary = {
        "worker": worker, "profile": profile,
        "count": len(SENTENCES), "chunk_type": str(settings.chunk_type),
        "compute_type": str(settings.compute_type),
        "inter_threads": settings.inter_threads, "intra_threads": settings.intra_threads,
        "batch_size": settings.batch_size,
        "translate_seconds": seconds,
        "peak_process_memory_mb": get_peak_mb(),
        "mechanical_flags": flagged,
        "translations": results,
        "provisional_only": True,
        "production_writes": 0,
        "private_ffh_data": 0,
    }
    print("R103_CHILD " + json.dumps(summary, ensure_ascii=False), flush=True)

def parent(worker, output_dir):
    out = Path(output_dir)
    out.mkdir(exist_ok=True, parents=True)
    import argostranslate.package as pkg
    pkg.update_package_index()
    model = next((x for x in pkg.get_available_packages() if
                  x.from_code == "en" and x.to_code == "es"), None)
    if model is None:
        raise RuntimeError("No direct Argos en-es package available")
    pkg.install_from_path(model.download())
    print("R103_MODEL_READY", json.dumps({"version": str(model.package_version),
                                          "worker": worker}), flush=True)
    profiles = [
        ("baseline", {}),
        ("minisbd", {
            "ARGOS_CHUNK_TYPE": "MINISBD",
        }),
        ("minisbd_int8", {
            "ARGOS_CHUNK_TYPE": "MINISBD",
            "ARGOS_COMPUTE_TYPE": "int8",
            "ARGOS_INTER_THREADS": "1",
            "ARGOS_INTRA_THREADS": "1",
            "ARGOS_BATCH_SIZE": "8",
            "OMP_NUM_THREADS": "1",
        }),
        ("default_int8", {
            "ARGOS_COMPUTE_TYPE": "int8",
            "ARGOS_INTER_THREADS": "1",
            "ARGOS_INTRA_THREADS": "1",
            "ARGOS_BATCH_SIZE": "8",
            "OMP_NUM_THREADS": "1",
        }),
    ]
    results = []
    env_base = os.environ.copy()
    for key in ("ARGOS_CHUNK_TYPE", "ARGOS_COMPUTE_TYPE", "ARGOS_INTER_THREADS",
                "ARGOS_INTRA_THREADS", "ARGOS_BATCH_SIZE"):
        env_base.pop(key, None)
    for name, options in profiles:
        env = dict(env_base)
        env.update(options)
        begun = time.monotonic()
        try:
            p = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "child",
                 "--profile", name, "--worker", worker],
                capture_output=True, text=True, timeout=180, env=env,
            )
            lines = [v[len("R103_CHILD "):] for v in p.stdout.splitlines()
                     if v.startswith("R103_CHILD ")]
            if p.returncode != 0 or len(lines) != 1:
                result = {"profile": name, "worker": worker, "ok": False,
                          "returncode": p.returncode,
                          "failure_excerpt": (p.stderr[-1800:] + p.stdout[-600:])[-1800:]}
            else:
                result = dict(json.loads(lines[0]), ok=True)
        except subprocess.TimeoutExpired:
            result = {"profile": name, "worker": worker, "ok": False,
                      "failure_excerpt": "timeout after 180s"}
        result["wall_seconds_including_process_start"] = round(time.monotonic() - begun, 2)
        results.append(result)
        print("R103_PROFILE", json.dumps({
            k: v for k, v in result.items() if k not in ("translations", "mechanical_flags")
        }, ensure_ascii=False), flush=True)
    baseline = results[0]
    for result in results[1:]:
        if result.get("ok") and baseline.get("ok"):
            result["output_difference_count_vs_baseline"] = sum(
                a != b for a,b in zip(result["translations"], baseline["translations"]))
    report = {"test": "FFH-R103-isolated-memory-profile", "worker": worker,
              "sample_count": len(SENTENCES), "profiles": results,
              "production_writes": 0, "approval_changes": 0,
              "only_synthetic_data": True,
              "notes": "Memory peak uses ru_maxrss per fresh child process. "
                       "Passing mechanical checks does not establish translation quality. "
                       "These GitHub runner measurements do not certify Render viability."}
    (out / "r103_profiles.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("R103_FINISHED", json.dumps({
        "worker": worker,
        "baseline_mb": baseline.get("peak_process_memory_mb"),
        "profiles": [
            {"name": r["profile"], "ok": r["ok"],
             "peak_mb": r.get("peak_process_memory_mb"),
             "seconds": r.get("translate_seconds"),
             "difference_count": r.get("output_difference_count_vs_baseline"),
             "flags": len(r.get("mechanical_flags", []))}
            for r in results]
    }), flush=True)
    if not baseline.get("ok"):
        raise RuntimeError("Baseline failed; no valid memory comparison")
    if not any(r.get("ok") for r in results[1:]):
        raise RuntimeError("All low-memory candidates failed")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("parent", "child"))
    ap.add_argument("--worker", choices=("A", "B"), required=True)
    ap.add_argument("--profile", default="baseline")
    ap.add_argument("--output-dir", default="r103-output")
    args = ap.parse_args()
    if args.mode == "child":
        child(args.profile, args.worker)
    else:
        parent(args.worker, args.output_dir)
