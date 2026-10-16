"""R118 offline admission/health soak. Synthetic inputs only. No FFH production.

Run inside one 512 MiB, 1 CPU disposable Docker container with networking
disabled. A single in-flight guarded request is allowed; overlapping requests
MUST fail immediately with 429 and health MUST remain responsive.
"""
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
from r123_readiness_gateway import Readiness, start_gateway

TARGET=os.environ.get("FFH_TARGET_LANGUAGE")
ROOT=Path("/srv/ffh")
OUT=ROOT/"r118-output"
BACKEND_URL="http://127.0.0.1:18781"
URL=BACKEND_URL
GATEWAY_STATE=Readiness()

def backend_health():
    with urllib.request.urlopen(BACKEND_URL+"/health",timeout=1.5) as r:
        return r.status == 200 and json.loads(r.read()).get("status")=="ok"
MIB=1024*1024
MEMORY_LIMIT=512*MIB
SOAK_SECONDS=120
# Unlike unsafe automatic per-request recycling, this test restarts the
# Gunicorn *master* only after all accepted requests have completed.
MAX_WORKER_REQUESTS=0
ROUNDS=4
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
        "--max-requests","0",
        "--max-requests-jitter","0",
        "--graceful-timeout","120",
        "--bind","127.0.0.1:18781","app:app"],
        cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    round_report={"index":index,"pid":proc.pid,"startup_seconds":None,
                  "cycles":0,"max_worker_requests":MAX_WORKER_REQUESTS}
    try:
        start=time.monotonic()
        while time.monotonic()-start<35:
            check(proc.poll() is None,"Gunicorn exited before ready")
            try:
                if backend_health():break
            except (OSError,ValueError):
                time.sleep(0.1)
        else:raise RuntimeError("Health timed out during startup")
        round_report["startup_seconds"]=round(time.monotonic()-start,3)
        GATEWAY_STATE.resume()
        check(http("/health")[0]==200, "Gateway never became ready")
        with urllib.request.urlopen(BACKEND_URL+"/",timeout=3) as meta_response:
            meta=json.loads(meta_response.read())
        check(meta["max_batch_items"]==25,"Legacy batch limit changed")
        # Quarantined stage routes must not run an unguarded model call.
        for old in ("/translate", "/translate-batch"):
            shape = {"source":"en","target":TARGET}
            if old=="/translate":
                shape["q"]="A fictional book has three pages."
            else:
                shape["items"]=["A fictional note."]
            stopped=http(old,shape)
            check(stopped[0]==410,"Legacy route bypassed quarantine")
        round_report["legacy_translation_routes_quarantined"]=2
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
        round_limit = min(deadline, START+SOAK_SECONDS*(index+1)/ROUNDS)
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
        # Assert no guarded request is still active before the orchestrator
        # deliberately shuts down this single master.
        lock_fd=os.open("/tmp/ffh-guarded-single-instance.lock",
                        os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            round_report["guarded_lock_idle_at_restart"]=True
        finally:
            os.close(lock_fd)
        check(GATEWAY_STATE.begin_drain(timeout=8),
              "A forwarded request was still active at planned shutdown")
        check(GATEWAY_STATE.snapshot()["active"]==0,
              "In-flight request count nonzero at planned shutdown")
        stopped = http("/experimental/guarded-translate", {
            "source":"en","target":TARGET,"q":"Invented client during restart gap."},5)
        check(stopped[0]==503 and stopped[1]["error"]=="service draining"
              and stopped[3].get("Retry-After")=="2",
              "Client in restart gap did not receive explicit 503")
        check(http("/health")[0]==503,
              "Readiness health incorrectly reported ready during drain")
        round_report["planned_gap_explicit_503"]=True
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
        round_report["automatic_restarts"]=log_data.count("Autorestarting worker")

def main():
    global URL
    check(TARGET in ("de","ko"),"R118 is targeted at the known problematic languages")
    check(cgroup("memory.max")==MEMORY_LIMIT,"Requires real 512 MiB cgroup")
    OUT.mkdir(parents=True,exist_ok=True)
    prev=events()
    gateway, gateway_thread = start_gateway(
        GATEWAY_STATE, backend_port=18781,
        stage_token=os.environ["FFH_GUARDED_STAGING_TOKEN"])
    URL="http://127.0.0.1:"+str(gateway.server_port)
    check(http("/health")[0]==503,"Gateway must be unavailable before first startup")
    report={"test":"R118-safe-2-minute-guarded-admission-soak","target":TARGET,
        "configured_batch":os.getenv("ARGOS_BATCH_SIZE"),
        "configured_worker_max_requests":MAX_WORKER_REQUESTS,
        "controlled_master_restarts":ROUNDS-1,
        "gateway":"loopback-only bounded readiness and drain proxy",
        "gateway_feature_production_enabled":False,
        "accepts_planned_restart_gap":True,
        "status":"NOT_RUN","human_approved":0,"production_writes":0,
        "network":"disabled","cache":False,"rounds":[],
        "busy_rejected":0,"items_processed":0,"accepted_batches":0,
        "provisional":0,"held":0,
        "health_during_seconds":[],"busy_response_seconds":[],"batch_seconds":[],
        "linguistic_accuracy_verified":False}
    try:
        deadline=time.monotonic()+SOAK_SECONDS
        for ix in range(ROUNDS):
            if ix:
                check(http("/experimental/guarded-translate",{
                    "source":"en","target":TARGET,
                    "q":"Imaginary client still waiting during startup gap."})[0]==503,
                    "Gateway forwarded request during pre-start interval")
            r=serve_one_round(ix,report,deadline)
            report["rounds"].append(r)
            print("R118_ROUND",json.dumps(r,sort_keys=True),flush=True)
        check(len(report["rounds"])==ROUNDS and
              len({r["pid"] for r in report["rounds"]})==ROUNDS,
              "Every master must be restarted between idle-only rounds")
        check(all(r.get("planned_gap_explicit_503") for r in report["rounds"]),
              "No explicit 503 evidence for some planned restart gaps")
        check(all(r.get("guarded_lock_idle_at_restart") for r in report["rounds"]),
              "An accepted guarded translation may still have been running")
        check(report["accepted_batches"]>=8,"Too few batches for sustained soak")
        check(all(r.get("worker_boots")==1 and
                  r.get("automatic_restarts")==0 for r in report["rounds"]),
              "Unexpected automatic worker recycling occurred")
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
        report["status"]="PASS_GATEWAY_DRAIN_PENDING_RESOURCE"
    except Exception as exc:
        report["status"]="HOLD_FAILURE"
        report["error_type"]=type(exc).__name__
        report["error_summary"]=str(exc)[:280]
        raise
    finally:
        gateway.shutdown()
        gateway.server_close()
        peak=cgroup("memory.peak")
        report["memory_peak_mib"]=round(peak/MIB,2)
        report["headroom_pct"]=round((MEMORY_LIMIT-peak)/MEMORY_LIMIT*100,2)
        latest=events()
        report["oom_kills"]=latest.get("oom_kill",0)-prev.get("oom_kill",0)
        report["total_seconds"]=round(time.monotonic()-START,2)
        report["gateway_snapshot"]=GATEWAY_STATE.snapshot()
        if report["oom_kills"] or report["headroom_pct"]<15:
            report["status"]="HOLD_MEMORY"
        elif report["status"]=="PASS_GATEWAY_DRAIN_PENDING_RESOURCE":
            report["status"]="PASS_GATEWAY_EXPLICIT_503_AND_RESOURCE_ONLY"
        (OUT/"summary.json").write_text(
            json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("R118_RESULT",json.dumps({k:v for k,v in report.items()
            if k not in ("health_during_seconds","busy_response_seconds",
                         "batch_seconds","rounds")},sort_keys=True),flush=True)
    check(report["oom_kills"]==0,"Out-of-memory kill detected")
    check(report["headroom_pct"]>=15,"Not enough memory headroom")

if __name__=="__main__":
    main()
