"""R125e: free-plan 0.1 CPU response/health diagnostic with real model.

Synthetic only; NEVER production, private users or translation approvals.
This benchmark measures (not guarantees) cold latency and simultaneous
backend /health while a 5-item protected batch uses 1 or 2 Gunicorn threads.
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
from r123h_memory_policy import memory_gate

ROOT=Path("/srv/ffh")
OUT=ROOT/"r125e-output"
MIB=1024*1024
LIMIT=512*MIB
TARGET="es"
PORT=18781
TOKEN=os.environ.get("FFH_GUARDED_STAGING_TOKEN","")
THREADS=int(os.environ.get("R125E_GUNICORN_THREADS","1"))
def ensure(x,msg):
    if not x:raise RuntimeError(msg)
def cgroup(k):
    s=(Path("/sys/fs/cgroup")/k).read_text().strip()
    ensure(s.isdecimal(),"Bad cgroup "+k)
    return int(s)
def oom():
    t=(Path("/sys/fs/cgroup")/"memory.events").read_text().splitlines()
    return int(next(z.split()[1] for z in t if z.startswith("oom_kill ")))
def query(path,content=None,timeout=105,with_token=True):
    body=None if content is None else json.dumps(content).encode()
    headers={"Content-Type":"application/json"} if body else {}
    if path.startswith("/experimental/guarded-") and with_token:
        headers["Authorization"]="Bearer "+TOKEN
    req=urllib.request.Request(f"http://127.0.0.1:{PORT}{path}",
        data=body,method="POST" if body else "GET",headers=headers)
    t=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=timeout) as res:
            return res.status,json.loads(res.read()),round(time.monotonic()-t,3)
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read()),round(time.monotonic()-t,3)

def main():
    ensure(THREADS in (1,2),"Only current-production 1 and staging 2 threads allowed")
    ensure(len(TOKEN)>=32,"Synthetic staging secret missing")
    ensure(cgroup("memory.max")==LIMIT,"Hard 512 MiB RAM required")
    ensure(cgroup("cpu.max") in (None,),"Unexpected missing CPU cgroup") if False else None
    cpu_max=(Path("/sys/fs/cgroup")/"cpu.max").read_text().split()
    ensure(len(cpu_max)==2 and cpu_max[0].isdigit() and cpu_max[1].isdigit()
           and int(cpu_max[0])*10==int(cpu_max[1]),
           "R125e requires exact 0.1 CPU throttling")
    OUT.mkdir(parents=True,exist_ok=True)
    before_oom=oom()
    report={"name":"R125e Free CPU 0.1 isolated one-model diagnostic",
            "target":TARGET,"cpu_limit":0.1,"threads":THREADS,
            "status":"NOT_STARTED","user_text":False,"approvals":0,
            "production_writes":0,"cache":False,"runtime_network":False}
    log=(OUT/"gunicorn.log").open("w")
    start=time.monotonic()
    proc=subprocess.Popen([sys.executable,"-m","gunicorn",
        "--workers","1","--threads",str(THREADS),"--timeout","180",
        "--max-requests","0","--bind",f"127.0.0.1:{PORT}","app:app"],
        cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    try:
        while time.monotonic()-start<105:
            ensure(proc.poll() is None,"Gunicorn died before startup")
            try:
                if query("/health",timeout=2)[0]==200:break
            except(OSError,ValueError):time.sleep(.1)
        else:raise RuntimeError("Cold start too slow")
        report["cold_ready_seconds"]=round(time.monotonic()-start,3)
        src={"source":"en","target":"es","q":"An imaginary red notebook is on a table."}
        single=query("/experimental/guarded-translate",src,timeout=105)
        ensure(single[0]==200 and single[1].get("human_approved") is False,
               "Single guarded provisional/held request failed")
        report["single_seconds"]=single[2]
        batch={"source":"en","target":"es","items":[
            {"id":str(i),"q":f"Imaginary shelf {i} contains seven books."}
            for i in range(5)]}
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(query,"/experimental/guarded-translate-batch",batch,150)
            time.sleep(.1)
            # Direct backend health (not only gateway's in-process READY bit).
            try:
                health=query("/health",timeout=5)
                report["backend_health_during_batch_code"]=health[0]
                report["backend_health_during_batch_seconds"]=health[2]
            except (TimeoutError,OSError) as error:
                report["backend_health_during_batch_code"]="TIMEOUT"
                report["backend_health_during_batch_seconds"]=5.0
            out=pending.result(timeout=160)
        ensure(out[0]==200 and out[1].get("count")==5,
               "Five synthetic guarded translation items did not finish")
        ensure(out[1].get("human_approved") is False and all(
               x.get("human_approved") is False for x in out[1]["results"]),
               "One of the model outputs was auto-approved")
        report["five_item_batch_seconds"]=out[2]
        report["five_item_results"]={k:sum(x["status"]==k for x in out[1]["results"])
                                    for k in ("held","provisional_candidate")}
        report["ready_after_batch"]=query("/health",timeout=5)[0]==200
        report["status"]="PASS_SYNTHETIC_CPU_DIAGNOSTIC_PENDING_RAM"
    except Exception as e:
        report["status"]="HOLD_RUNTIME"
        report["error_type"]=type(e).__name__
        report["error_summary"]=str(e)[:220]
        raise
    finally:
        if proc.poll() is None:proc.terminate()
        try:proc.wait(timeout=12)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait(timeout=3)
        log.close()
        peak=cgroup("memory.peak")
        report["peak_mib"]=round(peak/MIB,2)
        report["headroom_pct"]=round((LIMIT-peak)/LIMIT*100,2)
        report["oom_kills"]=oom()-before_oom
        if not memory_gate(peak,LIMIT,report["oom_kills"]):
            report["status"]="HOLD_RESOURCE"
        elif report["status"]=="PASS_SYNTHETIC_CPU_DIAGNOSTIC_PENDING_RAM":
            report["status"]="PASS_FREE_CPU_SYNTHETIC_ONLY"
        (OUT/"summary.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
        print("R125E_RESULT",json.dumps(report,sort_keys=True),flush=True)
    ensure(memory_gate(peak,LIMIT,report["oom_kills"]),
           "Free CPU diagnostic violated 20% memory headroom or zero-OOM gate")

if __name__=="__main__":
    main()
