"""R121: test-only real Flask/Gunicorn legacy-route quarantine, 512 MiB offline.

This tests source-level migration behavior with an invented note and no
production data. Both staging toggles are required. Not a public release.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path("/srv/ffh")
OUTPUT = ROOT / "r121-output"
URL = "http://127.0.0.1:18791"
MIB = 1024 * 1024

def must(condition, detail):
    if not condition: raise RuntimeError(detail)

def metric(name):
    value = (Path("/sys/fs/cgroup")/name).read_text().strip()
    must(value.isdecimal(), "A bounded cgroup metric is required: " + name)
    return int(value)

def get(path, body=None, bearer=True, timeout=95):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if data is not None else {}
    if bearer and path.startswith("/experimental/guarded-"):
        headers["Authorization"] = "Bearer "+os.environ["FFH_GUARDED_STAGING_TOKEN"]
    req = urllib.request.Request(URL+path,data=data,headers=headers,
                                 method="POST" if data is not None else "GET")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=timeout) as resp:
            return resp.status, json.loads(resp.read()), round(time.monotonic()-start,3),dict(resp.headers)
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read()), round(time.monotonic()-start,3),dict(err.headers)

def main():
    must(os.getenv("FFH_LEGACY_QUARANTINE_STAGING_ONLY")=="true",
         "Legacy quarantine test switch not enabled")
    must(os.getenv("FFH_GUARDED_API_STAGING_ONLY")=="true",
         "Guarded API test switch not enabled")
    must(len(os.environ.get("FFH_GUARDED_STAGING_TOKEN",""))>=32,
         "Missing test-only random bearer")
    must(metric("memory.max")==512*MIB,
         "R121 must run inside a real enforced 512MiB Docker cgroup")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    report={"test":"R121-real-Argos-staging-quarantine",
            "status":"NOT_YET_PASSED","target":os.getenv("FFH_TARGET_LANGUAGE"),
            "stage_auth":True,"legacy_quarantine":True,
            "private_text":False,"human_approvals":0,
            "production_writes":0,"netlify_deployments":0,
            "cache_enabled":False,"runtime_network":"disabled"}
    log=(OUTPUT/"gunicorn.log").open("w",encoding="utf-8")
    proc=subprocess.Popen([sys.executable,"-m","gunicorn",
        "--workers","1","--threads","2","--max-requests","12",
        "--max-requests-jitter","0","--timeout","120",
        "--bind","127.0.0.1:18791","app:app"],
        cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    started=time.monotonic()
    try:
        for _ in range(240):
            must(proc.poll() is None,"Gunicorn exited during startup")
            try:
                if get("/health",timeout=1)[0]==200:break
            except (OSError,ValueError):time.sleep(.1)
        else:
            raise RuntimeError("Health timeout")
        text="An imaginary notebook contains seven pages."
        single={"q":text,"source":"en","target":report["target"]}
        sample={"items":[{"id":str(i),
                          "q":f"Fictional library note {i} contains {i+4} pages."}
                         for i in range(25)],
                "source":"en","target":report["target"]}
        for path,data in (("/translate",single),("/translate-batch",sample)):
            for bearer in (True,False):
                code,body,_,_=get(path,data,bearer=bearer)
                must(code==410 and body=={
                    "error":"legacy translation route disabled in staging"},
                    "Legacy translation bypass detected: "+path)
        report["legacy_bypass_denied"]=4
        denied=get("/experimental/guarded-translate",single,bearer=False)
        must(denied[0]==401,"Guarded request did not enforce bearer auth")
        must("no-store" in denied[3].get("Cache-Control",""),
             "Unauthorized response could be cached")
        report["unauthorized_denied"]=1
        held=get("/experimental/guarded-translate",{
            **single,"q":"https://example.invalid/fictional-data"})
        must(held[0]==200 and held[1]["status"]=="held" and
             held[1]["draft"] is None,"URL was not held without a draft")
        report["held_url_without_draft"]=True
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(get,"/experimental/guarded-translate-batch",sample)
            time.sleep(.05)
            must(not pending.done(),"Batch finished before active health probe")
            health=get("/health",timeout=5)
            busy=get("/experimental/guarded-translate",single,timeout=5)
            translated=pending.result(timeout=100)
        must(health[0]==200 and health[2]<5,
             "Health failed while guarded batch was active")
        must(busy[0]==429 and busy[1].get("retry_after_seconds")==2,
             "Second guarded request not rejected with 429")
        must("no-store" in busy[3].get("Cache-Control",""),
             "Overload response could be cached")
        must(translated[0]==200 and translated[1]["count"]==25,
             "Protected full 25-item batch failed")
        rows=translated[1]["results"]
        must(len(rows)==25 and all(r["human_approved"] is False for r in rows),
             "Incorrect batch result count/review flag")
        must(all(r["draft"] is None if r["status"]=="held" else
                 isinstance(r.get("draft"),str) and bool(r["draft"].strip())
                 for r in rows),"Incorrect held/provisional drafts")
        report["translated_item_occurrences"]=25
        report["health_during_seconds"]=health[2]
        report["busy_seconds"]=busy[2]
        report["status"]="PASS_BEHAVIOR_PENDING_RESOURCE_LIMITS"
    except Exception as e:
        report["status"]="HOLD_BEHAVIOR"
        report["error_class"]=type(e).__name__
        report["error"]=str(e)[:260]
        raise
    finally:
        if proc.poll() is None:proc.terminate()
        try:proc.wait(timeout=9)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=3)
        log.close()
        peak=metric("memory.peak")/MIB
        report["memory_peak_mib"]=round(peak,2)
        report["memory_headroom_percent"]=round((512-peak)/512*100,2)
        report["wall_seconds"]=round(time.monotonic()-started,2)
        report["memory_event_oom_kill"]=next((
            int(line.split()[1]) for line in
            (Path("/sys/fs/cgroup")/"memory.events").read_text().splitlines()
            if line.startswith("oom_kill ")),None)
        if report["memory_headroom_percent"]<15 or report["memory_event_oom_kill"]:
            report["status"]="HOLD_MEMORY"
        (OUTPUT/"summary.json").write_text(
            json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("R121_REAL_RESULT",json.dumps(report,sort_keys=True),flush=True)
    must(report["memory_headroom_percent"]>=15,
         "Hard 512 MiB memory reserve gate failed")
    must(report["memory_event_oom_kill"]==0,"OOM kill observed")

if __name__=="__main__":
    main()
