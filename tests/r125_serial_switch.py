"""R125: test two installed models on DISK, one resident process at a time.

Synthetic text. Offline runtime. Hard 512MiB cgroup + 20% headroom.
This is not a production orchestrator, not authentication for FFH users,
not a deployable multi-language routing service.
"""
from __future__ import annotations
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

from r125_serial_gateway import Readiness, start_gateway
from r123h_memory_policy import memory_gate
# Running as tests/script.py does not add repository root to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.r119_verify_model_tree import verify

ROOT=Path("/srv/ffh")
MODELS=ROOT/"r125-models"
ACTIVE_LINK=ROOT/".argos"/"packages"
OUT=ROOT/"r125-output"
CONFIG={"es":(1,4),"fr":(8,4)}
SEQUENCE=("es","fr","es","fr")
TARGET_PORT=18781
MIB=1024*1024
LIMIT=512*MIB
TOKEN=os.environ.get("FFH_GUARDED_STAGING_TOKEN","")
START=time.monotonic()
SOAK_SECONDS=136

def ensure(x,msg):
    if not x: raise RuntimeError(msg)

def cgroup(name):
    path=Path("/sys/fs/cgroup")/name
    raw=path.read_text().strip()
    ensure(raw.isdecimal(),"Expected cgroup "+name)
    return int(raw)

def oom_count():
    lines=(Path("/sys/fs/cgroup")/"memory.events").read_text().splitlines()
    return int(next(l.split()[1] for l in lines if l.startswith("oom_kill ")))

def http(url,path,payload=None,token=TOKEN,timeout=95):
    body=None if payload is None else json.dumps(payload).encode()
    headers={"Content-Type":"application/json"} if body is not None else {}
    if path.startswith("/experimental/guarded-") and token is not None:
        headers["Authorization"]="Bearer "+token
    req=urllib.request.Request(url+path,data=body,
        method="POST" if body is not None else "GET",headers=headers)
    start=time.monotonic()
    try:
        with urllib.request.urlopen(req,timeout=timeout) as res:
            return res.status,json.loads(res.read()),time.monotonic()-start,dict(res.headers)
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read()),time.monotonic()-start,dict(e.headers)

def items(target,index):
    base=index*1000
    return [{"id":str(base+i),
             "q":f"Imaginary {target} book number {base+i} has seven pages."}
            for i in range(23)]+[
                {"id":str(base+23),"q":"Book {{EXPERIMENT_ID}} is blue."},
                {"id":str(base+24),"q":"See https://example.invalid/fiction."}
            ]

def select_model(target, baselines):
    ensure(target in CONFIG,"Unsupported R125 target")
    p=MODELS/target
    ensure(p.is_dir() and not p.is_symlink(),"Missing isolated model directory")
    match=verify(target,p,baselines)
    ensure(match["release_certified"] is False,"Misleading model certification")
    tmp=ROOT/".argos"/"r125-next-model"
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    os.symlink(str(p),tmp)
    os.replace(tmp,ACTIVE_LINK)
    ensure(ACTIVE_LINK.is_symlink() and ACTIVE_LINK.resolve()==p,
           "Model path switch was not atomic/exact")
    return match

def main():
    ensure(len(TOKEN)>=32,"Synthetic staging bearer required")
    ensure(cgroup("memory.max")==LIMIT,"Require enforced 512MiB cgroup")
    OUT.mkdir(parents=True,exist_ok=True)
    before_oom=oom_count()
    with (ROOT/"models"/"r119_observed_model_trees.json").open() as f:
        baselines=json.load(f)
    for lang in CONFIG:
        ensure((MODELS/lang).is_dir(),"Missing staged language package")
    state=Readiness()
    server,worker=start_gateway(state,backend_port=TARGET_PORT,stage_token=TOKEN)
    url="http://127.0.0.1:"+str(server.server_port)
    report={"test":"R125 two model packages one active resident",
            "status":"NOT_STARTED","models_on_disk":list(CONFIG),
            "language_sequence":list(SEQUENCE),
            "inference_profiles":{x:{"batch":CONFIG[x][0],"beam":CONFIG[x][1]}
                                  for x in CONFIG},
            "permitted_peak_mib":409.6,"headroom_min_pct":20,
            "model_loading":"fresh single Gunicorn process per selected model",
            "cache":False,"production_writes":0,"human_approvals":0,
            "no_runtime_network":True,"rounds":[],"items":0,
            "held":0,"provisional":0,"busy_429":0,
            "explicit_503":0,"wrong_target_503":0,
            "previous_master_exited_before_next":True}
    proc=None
    try:
        ensure(http(url,"/health")[0]==503,"Initially unavailable gateway required")
        report["explicit_503"]+=1
        end=time.monotonic()+SOAK_SECONDS
        for index,target in enumerate(SEQUENCE):
            ensure(proc is None,"Two backends must never overlap")
            ensure(state.snapshot()["ready"] is False and
                   state.snapshot()["active"]==0,
                   "Switch attempted with active clients")
            stored=select_model(target,baselines)
            state.choose_target(target)
            # Intentionally send during startup gap; must receive bounded 503.
            check=http(url,"/experimental/guarded-translate",
                {"source":"en","target":target,"q":"Imaginary note during startup."},timeout=5)
            ensure(check[0]==503 and check[3].get("Retry-After")=="2",
                   "Startup accepted text before model health check")
            report["explicit_503"]+=1
            batch,beam=CONFIG[target]
            env=os.environ.copy()
            env.update({"FFH_TARGET_LANGUAGE":target,
                        "ARGOS_BATCH_SIZE":str(batch),
                        "ARGOS_BEAM_SIZE":str(beam),
                        "FFH_MULTILINGUAL":"false",
                        "FFH_TRANSLATION_CACHE_ENABLED":"false"})
            logfile=OUT/f"gunicorn-switch-{index}.log"
            out=open(logfile,"w",encoding="utf-8")
            proc=subprocess.Popen([sys.executable,"-m","gunicorn",
                "--workers","1","--threads","2","--timeout","120",
                "--max-requests","0","--graceful-timeout","120",
                "--bind",f"127.0.0.1:{TARGET_PORT}","app:app"],
                cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT)
            round_info={"index":index,"target":target,"master_pid":proc.pid,
                        "tree_sha256":stored["tree_sha256"],"items":0,"batches":0,
                        "busy_429":0,"wrong_target_503":0}
            try:
                start=time.monotonic()
                for _ in range(300):
                    ensure(proc.poll() is None,"Backend died before ready")
                    try:
                        health=http(f"http://127.0.0.1:{TARGET_PORT}",
                                    "/health",timeout=1)
                        if health[0]==200 and health[1].get("configured_target")==target:
                            break
                    except (OSError,ValueError):
                        time.sleep(.1)
                else:raise RuntimeError("Backend never became healthy")
                round_info["startup_seconds"]=round(time.monotonic()-start,3)
                state.resume()
                ensure(http(url,"/health")[0]==200,"Gateway not ready after model health")
                wrong="fr" if target=="es" else "es"
                rejected=http(url,"/experimental/guarded-translate",
                    {"source":"en","target":wrong,"q":"Wrong language must never route."},timeout=5)
                ensure(rejected[0]==503 and rejected[1].get("error")==
                       "target model not resident" and
                       rejected[3].get("Retry-After")=="2",
                       "Wrong model was not explicitly rejected")
                round_info["wrong_target_503"]+=1
                report["wrong_target_503"]+=1
                ensure(http(url,"/translate",{"source":"en","target":target,
                       "q":"Must not reach legacy route."})[0]==410,
                       "Legacy translation bypass")
                ensure(http(url,"/experimental/guarded-translate",
                    {"source":"en","target":target,"q":"Unauthorized"},
                    token="wrong-token")[0]==401,"Bad bearer unexpectedly accepted")
                slice_end=min(end,START+SOAK_SECONDS*(index+1)/len(SEQUENCE))
                count=0
                while time.monotonic()<slice_end or count==0:
                    fixture=items(target,index*100+count)
                    data={"source":"en","target":target,"items":fixture}
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        pending=executor.submit(http,url,
                            "/experimental/guarded-translate-batch",data,TOKEN,110)
                        time.sleep(.085)
                        ensure(not pending.done(),
                            "Concurrent batch completed before 429 challenge")
                        busy=http(url,"/experimental/guarded-translate",
                            {"source":"en","target":target,"q":"Competing fake note."},
                            timeout=5)
                        healthy=http(url,"/health",timeout=5)
                        completed=pending.result(timeout=115)
                    ensure(busy[0]==429 and busy[3].get("Retry-After")=="2",
                           "Overlapping translation not rejected")
                    ensure(healthy[0]==200 and healthy[2]<5,
                           "Gateway health starved during translation")
                    status,payload,secs,_=completed
                    ensure(status==200 and payload.get("count")==25,
                           "Full 25-item guarded model batch failed")
                    rows=payload["results"]
                    ensure(len(rows)==25 and
                           [r["id"] for r in rows]==[x["id"] for x in fixture],
                           "Guarded translation batch identifiers corrupted")
                    ensure(payload.get("human_approved") is False,
                           "Batch was unexpectedly approved")
                    for entry in rows:
                        ensure(entry["human_approved"] is False and
                               entry["production_writes"]==0,
                               "Automatic approval or DB write")
                        if entry["status"]=="held":
                            ensure(entry["draft"] is None,"Held draft exposed")
                            report["held"]+=1
                        else:
                            ensure(entry["status"]=="provisional_candidate"
                                   and isinstance(entry["draft"],str)
                                   and entry["draft"].strip(),
                                   "Bad provisional output")
                            report["provisional"]+=1
                    count+=1
                    round_info["items"]+=25
                    round_info["batches"]+=1
                    round_info["busy_429"]+=1
                    report["items"]+=25
                    report["busy_429"]+=1
                    if count>=50:break
                # Set gateway UNAVAILABLE before waiting for in-flight clients.
                ensure(state.begin_drain(timeout=12),"Drain failed")
                ensure(state.snapshot()["active"]==0,"In-flight during switch")
                fd=os.open("/tmp/ffh-guarded-single-instance.lock",
                           os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
                try:
                    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    fcntl.flock(fd,fcntl.LOCK_UN)
                finally:
                    os.close(fd)
                paused=http(url,"/experimental/guarded-translate",
                    {"source":"en","target":target,"q":"Fake request during shutdown"},
                    timeout=5)
                ensure(paused[0]==503 and paused[3].get("Retry-After")=="2",
                       "Shutdown interval must return explicit 503")
                report["explicit_503"]+=1
                round_info["drained_before_shutdown"]=True
            finally:
                if proc.poll() is None:proc.terminate()
                try:proc.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait(timeout=4)
                round_info["exit_code"]=proc.returncode
                proc=None
                out.close()
                log_text=logfile.read_text()
                round_info["worker_boots"]=log_text.count("Booting worker with pid")
                round_info["automatic_restarts"]=log_text.count("Autorestarting worker")
                report["rounds"].append(round_info)
                print("R125_ROUND",json.dumps(round_info,sort_keys=True),flush=True)
            ensure(round_info["exit_code"]==0 and
                   round_info["worker_boots"]==1 and
                   round_info["automatic_restarts"]==0,
                   "Master process did not terminate cleanly")
        ensure(len(report["rounds"])==len(SEQUENCE) and
               len({x["master_pid"] for x in report["rounds"]})==len(SEQUENCE),
               "Expected four separate model processes")
        ensure(all(r["batches"]>=1 for r in report["rounds"]),
               "At least one complete batch per selected model is required")
        ensure(report["items"]==report["busy_429"]*25 and
               report["held"]+report["provisional"]==report["items"],
               "Missing real translation items or overload checks")
        report["status"]="PASS_SWITCH_AND_API_PENDING_MEMORY"
    except Exception as e:
        report["status"]="HOLD_BEHAVIOR"
        report["error_type"]=type(e).__name__
        report["error_summary"]=str(e)[:240]
        raise
    finally:
        if proc is not None:
            proc.kill();proc.wait(timeout=5)
        server.shutdown();server.server_close()
        peak=cgroup("memory.peak")
        report["memory_peak_mib"]=round(peak/MIB,2)
        report["headroom_pct"]=round((LIMIT-peak)/LIMIT*100,2)
        report["oom_kills"]=oom_count()-before_oom
        report["wall_seconds"]=round(time.monotonic()-START,2)
        report["gateway_snapshot"]=state.snapshot()
        if not memory_gate(peak,LIMIT,report["oom_kills"]):
            report["status"]="HOLD_MEMORY"
        elif report["status"]=="PASS_SWITCH_AND_API_PENDING_MEMORY":
            report["status"]="PASS_SINGLE_INSTANCE_TWO_MODEL_SWITCH_RESOURCE_ONLY"
        (OUT/"summary.json").write_text(
            json.dumps(report,indent=2,sort_keys=True)+"\n")
        print("R125_RESULT",json.dumps({k:v for k,v in report.items() if k!="rounds"},
                                       sort_keys=True),flush=True)
    ensure(memory_gate(peak,LIMIT,report["oom_kills"]),
           "R125 memory less than 20% headroom, or OOM kill")

if __name__=="__main__":
    main()
