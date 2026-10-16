"""R118 offline admission/health soak. Synthetic inputs only. No FFH production.

Run inside one 512 MiB, 1 CPU disposable Docker container with networking
disabled. A single in-flight guarded request is allowed; overlapping requests
MUST fail immediately with 429 and health MUST remain responsive.
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

TARGET=os.environ.get("FFH_TARGET_LANGUAGE")
ROOT=Path("/srv/ffh")
OUT=ROOT/"r118-output"
URL="http://127.0.0.1:18781"
MIB=1024*1024
MEMORY_LIMIT=512*MIB
SOAK_SECONDS=120
MAX_WORKER_REQUESTS=int(os.environ.get("R119_TEST_MAX_REQUESTS","0"))
if MAX_WORKER_REQUESTS not in (12,24):
    raise ValueError("R119b requires precisely 12 or 24 worker requests")
START=time.monotonic()

def check(value,message):
    if not value: raise RuntimeError(message)

def cgroup(name):
    p=Path("/sys/fs/cgroup")/name
    check(p.is_file(),f"Missing cgroup: {name}")
    raw=p.read_text().strip()
    check(raw.isdecimal(),f"Invalid cgroup: {name}")
    return int(raw)

def events():
    return {p[0]:int(p[1]) for line in (Path("/sys/fs/cgroup")/"memory.events").read_text().splitlines() if len(p:=line.split())==2}

def http(path,payload=None,timeout=110):
    data=None if payload is None else json.dumps(payload).encode()
    headers={"Content-Type":"application/json"} if data is not None else {}
    if path.startswith("/experimental/guarded-"):
        token=os.environ.get("FFH_GUARDED_STAGING_TOKEN","")
        check(len(token)>=32,"No test-only staging bearer configured")
        headers["Authorization"]="Bearer "+token
    req=urllib.request.Request(URL+path,data=data,
        method="POST" if data is not None else "GET",
        headers=headers)
    t=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=timeout) as res:
            return res.status,json.loads(res.read()),time.monotonic()-t,dict(res.headers)
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read()),time.monotonic()-t,dict(e.headers)

def test_items(round_no,iteration):
    base=round_no*1000+iteration*25
    texts=[{"id":str(base+i),
        "q":f"Imaginary library record {base+i} has {base+i+7} handwritten pages."}
        for i in range(21)]
    texts.extend([
        {"id":f"p{base}","q":"Card {{ROW_ID}} is on the table."},
        {"id":f"p{base+1}","q":"The book {{BATCH_ID}} has a blue cover."},
        {"id":f"bad{base}","q":"{{invalid}}"},
        {"id":f"url{base}","q":"Visit https://example.invalid."}
    ])
    check(len(texts)==25,"Fixture must have exactly 25 items")
    return texts

def guarded(items):
    return {"source":"en","target":TARGET,"items":items}

def validate_batch(reply,expected_ids,summary):
    status,obj,seconds,_=reply
    check(status==200 and obj.get("count")==25,"Failed full guarded batch")
    entries=obj.get("results",[])
    check([row["id"] for row in entries]==expected_ids,"Batch IDs changed")
    check(obj.get("human_approved") is False,"Batch auto-reviewed")
    for row in entries:
        check(row["status"] in ("held","provisional_candidate"),"Unrecognized candidate status")
        check(row.get("human_approved") is False and row.get("production_writes")==0,
              "Automated approval/write marker")
        if row["status"]=="held":
            check(row["draft"] is None,"Held candidate leaked draft")
            summary["held"]+=1
        else:
            check(isinstance(row.get("draft"),str) and row["draft"].strip(),
                  "Provisional candidate blank")
            summary["provisional"]+=1
    summary["accepted_batches"]+=1
    summary["items_processed"]+=len(entries)
    summary["batch_seconds"].append(round(seconds,3))

def serve_one_round(index,report,deadline):
    log=(OUT/f"gunicorn-{index}.log").open("w",encoding="utf-8")
    env=os.environ.copy()
    env.update({"FFH_GUARDED_API_STAGING_ONLY":"true",
                "FFH_TRANSLATION_CACHE_ENABLED":"false",
                "FFH_MULTILINGUAL":"false"})
    proc=subprocess.Popen([sys.executable,"-m","gunicorn",
        "--workers","1","--threads","2","--timeout","120",
        "--max-requests",str(MAX_WORKER_REQUESTS),
        "--max-requests-jitter","0",
        "--bind","127.0.0.1:18781","app:app"],
        cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    round_report={"index":index,"pid":proc.pid,"startup_seconds":None,
                  "cycles":0,"max_worker_requests":MAX_WORKER_REQUESTS}
    try:
        start=time.monotonic()
        while time.monotonic()-start<35:
            check(proc.poll() is None,"Gunicorn exited before ready")
            try:
                if http("/health",timeout=1.5)[0]==200:break
            except (OSError,ValueError):
                time.sleep(0.1)
        else:raise RuntimeError("Health timed out during startup")
        round_report["startup_seconds"]=round(time.monotonic()-start,3)
        check(http("/")[1]["max_batch_items"]==25,"Legacy batch limit changed")
        # Validate that the real Gunicorn service blocks a fake credential.
        bad_request=urllib.request.Request(
            URL+"/experimental/guarded-translate",
            data=json.dumps({"q":"synthetic note","source":"en","target":TARGET}).encode(),
            method="POST",headers={"Content-Type":"application/json",
                                    "Authorization":"Bearer invalid"})
        try:
            urllib.request.urlopen(bad_request,timeout=4)
            raise RuntimeError("Bad credential unexpectedly accepted")
        except urllib.error.HTTPError as forbidden:
            check(forbidden.code==401,"Wrong unauthorized status")
            check("no-store" in forbidden.headers.get("Cache-Control",""),
                  "Unauthorized guarded HTTP response may be cached")
        round_report["unauthorized_http"]=401
        round_limit=deadline if index==1 else START+SOAK_SECONDS/2
        while time.monotonic()<round_limit:
            items=test_items(index,round_report["cycles"])
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(http,"/experimental/guarded-translate-batch",
                                    guarded(items),110)
                time.sleep(0.08)
                check(not pending.done(),"Batch finished before contention test")
                busy=http("/experimental/guarded-translate",{
                    "q":"A second invented notebook.","source":"en","target":TARGET},5)
                health=http("/health",timeout=5)
                finished=pending.result(timeout=120)
            check(busy[0]==429,"Second guarded request did not fail fast with 429")
            check("no-store" in busy[3].get("Cache-Control",""),
                  "Busy response must not be cached")
            check(busy[1]=={"error":"translation service busy",
                "retryable":True,"retry_after_seconds":2},"Invalid overload payload")
            check(busy[3].get("Retry-After")=="2","Missing retry header")
            check(busy[2]<1.5,"429 overload response too slow")
            check(health[0]==200 and health[2]<5,"Health starved by translation")
            report["health_during_seconds"].append(round(health[2],4))
            report["busy_response_seconds"].append(round(busy[2],4))
            report["busy_rejected"]+=1
            validate_batch(finished,[row["id"] for row in items],report)
            round_report["cycles"]+=1
            if round_report["cycles"]>80: break

        # API recovery after last translation, with guarded integrity intact.
        after=http("/experimental/guarded-translate",{
            "q":"The bookmark {{SAMPLE_ID}} is in a drawer.",
            "source":"en","target":TARGET},90)
        check(after[0]==200,"Guard failed after soak")
        if after[1].get("status")=="provisional_candidate":
            check("{{SAMPLE_ID}}" in after[1]["draft"],"Placeholder corruption")
        else:
            check(after[1]["draft"] is None,"Held draft leaked")
        check(http("/health",timeout=5)[0]==200,"Health failed after soak")
        return round_report
    finally:
        if proc.poll() is None:proc.terminate()
        try:proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        round_report["exit_code"]=proc.returncode
        log.close()
        log_data=(OUT/f"gunicorn-{index}.log").read_text(encoding="utf-8")
        round_report["worker_boots"]=log_data.count("Booting worker with pid")

def main():
    check(TARGET in ("de","ko"),"R118 is targeted at the known problematic languages")
    check(cgroup("memory.max")==MEMORY_LIMIT,"Requires real 512 MiB cgroup")
    OUT.mkdir(parents=True,exist_ok=True)
    prev=events()
    report={"test":"R118-safe-2-minute-guarded-admission-soak","target":TARGET,
        "configured_batch":os.getenv("ARGOS_BATCH_SIZE"),
        "configured_worker_max_requests":MAX_WORKER_REQUESTS,
        "status":"NOT_RUN","human_approved":0,"production_writes":0,
        "network":"disabled","cache":False,"rounds":[],
        "busy_rejected":0,"items_processed":0,"accepted_batches":0,
        "provisional":0,"held":0,
        "health_during_seconds":[],"busy_response_seconds":[],"batch_seconds":[],
        "linguistic_accuracy_verified":False}
    try:
        deadline=time.monotonic()+SOAK_SECONDS
        for ix in range(2):
            r=serve_one_round(ix,report,deadline)
            report["rounds"].append(r)
            print("R118_ROUND",json.dumps(r,sort_keys=True),flush=True)
        check(len(report["rounds"])==2 and
              report["rounds"][0]["pid"]!=report["rounds"][1]["pid"],
              "Restart did not occur")
        check(report["accepted_batches"]>=8,"Too few batches for sustained soak")
        check(all(r.get("worker_boots",0)>=2 for r in report["rounds"]),
              "Gunicorn did not demonstrate repeated worker recycling")
        check(report["busy_rejected"]==report["accepted_batches"],
              "Not all overlapping requests were safely rejected")
        check(report["items_processed"]==report["accepted_batches"]*25,
              "Missing translated batch results")
        result=sorted(report["health_during_seconds"])
        report["health_p95_seconds"]=result[int(.95*(len(result)-1))]
        report["health_max_seconds"]=max(result)
        report["busy_response_max_seconds"]=max(report["busy_response_seconds"])
        check(report["health_p95_seconds"]<=2.0,"Health p95 >2s")
        check(report["health_max_seconds"]<5,"Health max >=5s")
        report["status"]="PASS_ADMISSION_AND_RESOURCE_PENDING_FINAL_CGROUP"
    except Exception as exc:
        report["status"]="HOLD_FAILURE"
        report["error_type"]=type(exc).__name__
        report["error_summary"]=str(exc)[:280]
        raise
    finally:
        peak=cgroup("memory.peak")
        report["memory_peak_mib"]=round(peak/MIB,2)
        report["headroom_pct"]=round((MEMORY_LIMIT-peak)/MEMORY_LIMIT*100,2)
        latest=events()
        report["oom_kills"]=latest.get("oom_kill",0)-prev.get("oom_kill",0)
        report["total_seconds"]=round(time.monotonic()-START,2)
        if report["oom_kills"] or report["headroom_pct"]<15:
            report["status"]="HOLD_MEMORY"
        (OUT/"summary.json").write_text(
            json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("R118_RESULT",json.dumps({k:v for k,v in report.items()
            if k not in ("health_during_seconds","busy_response_seconds",
                         "batch_seconds","rounds")},sort_keys=True),flush=True)
    check(report["oom_kills"]==0,"Out-of-memory kill detected")
    check(report["headroom_pct"]>=15,"Not enough memory headroom")

if __name__=="__main__":
    main()
