"""R113: Single-language offline cgroup/Gunicorn QA matrix. Synthetic inputs only.

Run solely in a disposable Docker container with --memory=512m --network none.
One target language per image; all outputs provisional, never approved.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

TARGETS = {"fr", "ja", "de", "ar", "tl", "ko", "vi", "zh"}
TARGET = os.environ.get("FFH_TARGET_LANGUAGE", "")
OUT = Path("/srv/ffh/r113-output")
ROOT = Path("/srv/ffh")
URL = "http://127.0.0.1:18753"
NUMBERS = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?")
MARKERS = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")
MiB = 1024 * 1024
START = time.monotonic()


def require(ok, detail):
    if not ok:
        raise RuntimeError(detail)


def cstat(name):
    path = Path("/sys/fs/cgroup") / name
    require(path.exists(), "Missing cgroup metric " + name)
    text = path.read_text().strip()
    require(text.isdigit(), "Unbounded or invalid cgroup metric " + name)
    return int(text)


def events():
    return {line.split()[0]: int(line.split()[1]) for line in
            (Path("/sys/fs/cgroup") / "memory.events").read_text().splitlines()}


def http(path, payload=None, timeout=90):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        URL + path, data=data, method="POST" if data else "GET",
        headers={"Content-Type": "application/json"} if data else {},
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read()), round(
                time.monotonic()-t0, 3)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read()), round(time.monotonic()-t0, 3)


def get_package_sha():
    root = ROOT / ".argos" / "packages"
    files = sorted(p for p in root.rglob("*") if p.is_file())
    require(bool(files), "Missing installed Argos package files")
    total = 0
    combined = hashlib.sha256()
    details = []
    for path in files:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            while True:
                data = fh.read(1024*1024)
                if not data:
                    break
                h.update(data)
                total += len(data)
        rel = str(path.relative_to(root))
        combined.update(rel.encode()+b"\0"+h.hexdigest().encode()+b"\n")
        details.append({"relative_path": rel, "sha256": h.hexdigest(),
                        "size_bytes": path.stat().st_size})
    return {"file_count": len(details), "total_bytes": total,
            "manifest_sha256": combined.hexdigest(),
            "largest_files": sorted(details,key=lambda d:d["size_bytes"],reverse=True)[:5]}


def check(source, translated):
    issues = []
    if not isinstance(translated, str) or not translated.strip():
        return ["empty"]
    if source.strip() == translated.strip():
        issues.append("unchanged")
    if sorted(NUMBERS.findall(source)) != sorted(NUMBERS.findall(translated)):
        issues.append("number_mismatch")
    if sorted(MARKERS.findall(source)) != sorted(MARKERS.findall(translated)):
        issues.append("placeholder_mismatch")
    return issues


def fixtures():
    return [
        "The blue notebook is on the table.",
        "Please open page 17 of the imaginary library record.",
        "There are 4 clean empty jars on the shelf.",
        "Measure 25 g of paper for a fictional art project.",
        "The test folder contains 120 files.",
        "A child reads a book in the quiet classroom.",
        "The teacher writes the date on the label.",
        "This is example {{SAMPLE_ID}} for the fictional database.",
        "The drawing shows 8 flowers and 2 birds.",
        "The empty wooden box is near the window.",
    ]


def main():
    require(TARGET in TARGETS, "Invalid test target: " + TARGET)
    OUT.mkdir(parents=True, exist_ok=True)
    result = {
        "test": "R113-eight-languages-single-model-512m",
        "target": TARGET, "scope": "isolated synthetic CI only",
        "production_writes": 0, "netlify_deployments": 0,
        "human_approved": 0, "cache_enabled": False,
        "runtime_network": "none", "status": "INCOMPLETE",
        "license_reviewed": False, "linguistic_quality_reviewed": False,
        "model_single_language": True,
    }
    proc = None
    log = None
    begin_events = events()
    try:
        require(cstat("memory.max") == 512 * MiB,
                "Must run inside enforced 512 MiB memory cap")
        import importlib.metadata as im
        result["translator_version"] = im.version("argostranslate")
        require(result["translator_version"] == "1.11.0+ffhlite1",
                "Unexpected lightweight Argos build")
        result["model_manifest"] = get_package_sha()
        import argostranslate.package as pkg
        installed = [(p.from_code,p.to_code,str(p.package_version))
                     for p in pkg.get_installed_packages()]
        require(len(installed)==1 and installed[0][:2]==("en",TARGET),
                "Exactly one English target model must be installed")
        result["installed_models"] = installed
        result["stanza_loaded"] = "stanza" in sys.modules
        result["torch_loaded"] = "torch" in sys.modules
        require(not result["stanza_loaded"] and not result["torch_loaded"],
                "Heavy dependencies unexpectedly loaded")
        log = (OUT/"gunicorn.log").open("w", encoding="utf-8")
        proc = subprocess.Popen([
            sys.executable,"-m","gunicorn","--workers","1",
            "--threads","2","--timeout","120","--bind","127.0.0.1:18753","app:app",
        ], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        t0 = time.monotonic()
        while time.monotonic()-t0<40:
            require(proc.poll() is None, "Gunicorn stopped during startup")
            try:
                status,payload,_ = http("/health",timeout=2)
                if status==200 and payload.get("status")=="ok":
                    break
            except (OSError, ValueError):
                time.sleep(0.1)
        else:
            raise RuntimeError("Health failed to start within 40 seconds")
        result["startup_seconds"] = round(time.monotonic()-t0,3)
        status,meta,_ = http("/")
        require(status==200 and meta.get("configured_target")==TARGET,
                "Wrong translation target")
        require(meta.get("available_targets")==[TARGET],
                "Other translation models loaded or exposed")
        texts=fixtures()
        inputs=[{"id":str(i),"q":item} for i,item in enumerate(texts)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            pending=pool.submit(http,"/translate-batch",{
                "items":inputs,"source":"en","target":TARGET},115)
            time.sleep(0.05)
            result["batch_active_during_health"] = not pending.done()
            health_code,health,health_s=http("/health",timeout=6)
            result["health_during_batch_http"]=health_code
            result["health_during_batch_seconds"]=health_s
            status,data,elapsed=pending.result(timeout=120)
        require(status==200 and data.get("count")==len(texts),
                "Batch request failed")
        outputs=data.get("results",[])
        require(len(outputs)==len(texts) and all(v.get("ok") for v in outputs),
                "Batch produced item failures")
        require([v["id"] for v in outputs]==[str(i) for i in range(len(texts))],
                "Batch response order or IDs changed")
        checks=[]
        for text,row in zip(texts,outputs):
            flags=check(text,row.get("translatedText"))
            checks.append({"id":row["id"],"flags":flags})
        result["mechanical_flags"]={key:sum(key in v["flags"] for v in checks)
             for key in ("empty","unchanged","number_mismatch","placeholder_mismatch")}
        result["batch_seconds"]=elapsed
        result["batch_item_count"]=len(outputs)
        result["provisional_candidates"]=sum(not v["flags"] for v in checks)
        result["held_for_review"]=sum(bool(v["flags"]) for v in checks)
        result["health_after_batch_http"]=http("/health")[0]
        require(health_code==200 and result["health_after_batch_http"]==200,
                "Service unhealthy during/after batch")
        require(result["batch_active_during_health"],
                "Health probe did not overlap active batch")
        para = (
            "In this imaginary city the library opens every morning. "
            "A group of students reads about painting, architecture, and history. "
            "There is a large table near the window with many colorful books. "
            "A teacher writes notes in a blue notebook and shows the class a map. "
            "After the lesson everyone closes the books and returns to the classroom. "
        )*2
        status,long_result,elapsed=http("/translate",{
            "q":para,"source":"en","target":TARGET},timeout=110)
        require(status==200 and bool(long_result.get("translatedText","").strip()),
                "Long-form translation failed")
        result["long_paragraph_source_chars"]=len(para)
        result["long_paragraph_translation_seconds"]=elapsed
        result["long_paragraph_flags"]=check(para,long_result["translatedText"])
        result["invalid_body_status"]=http("/translate",["array is invalid"])[0]
        result["overlimit_status"]=http("/translate-batch",{
            "items":["example"]*26,"source":"en","target":TARGET})[0]
        require(result["invalid_body_status"]==400 and result["overlimit_status"]==400,
                "Invalid input not rejected")
        result["status"]="PASS_RESOURCE_API_PROVISIONAL_ONLY"
    except Exception as exc:
        result["status"]="FAIL"
        result["error_type"]=type(exc).__name__
        result["error_detail"]=str(exc)[:500]
        raise
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            result["gunicorn_exit"]=proc.returncode
        if log is not None:
            log.close()
        result["cgroup_peak_mib"]=round(cstat("memory.peak")/MiB,2)
        result["headroom_percent"]=round((512-result["cgroup_peak_mib"])/512*100,2)
        end_events=events()
        result["oom_kill_delta"]=end_events.get("oom_kill",0)-begin_events.get("oom_kill",0)
        result["elapsed_seconds"]=round(time.monotonic()-START,3)
        (OUT/"summary.json").write_text(
            json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+"\n",
            encoding="utf-8")
        print("R113_MODEL_RESULT",json.dumps({
            k:v for k,v in result.items() if k not in ("model_manifest",)
        },sort_keys=True,ensure_ascii=False),flush=True)
    require(result["oom_kill_delta"]==0,"OOM kill recorded")
    require(result["headroom_percent"]>=15,"Insufficient 15% memory headroom")


if __name__=="__main__":
    main()
