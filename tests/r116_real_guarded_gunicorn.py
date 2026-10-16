"""R116: real Argos + Gunicorn guarded-HTTP QA in network-disabled 512MiB Docker.
Entirely invented inputs; no FFH database, no user information, no approvals.
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

TARGET = os.environ.get("FFH_TARGET_LANGUAGE","")
URL = "http://127.0.0.1:18761"
OUT = Path("/srv/ffh/r116-output")
MiB = 1024*1024
START=time.monotonic()
SINGLE="/experimental/guarded-translate"
BATCH="/experimental/guarded-translate-batch"


def must(ok,message):
    if not ok:
        raise RuntimeError(message)


def metric(name):
    p=Path("/sys/fs/cgroup")/name
    must(p.is_file(), "Missing cgroup metric: "+name)
    val=p.read_text().strip()
    must(val.isdigit(), "Invalid cgroup metric "+name)
    return int(val)


def events():
    return {k:int(v) for k,v in
            (line.split() for line in (Path("/sys/fs/cgroup")/
                                       "memory.events").read_text().splitlines())}


def http(path,data=None,timeout=100):
    body=json.dumps(data).encode() if data is not None else None
    request=urllib.request.Request(URL+path,data=body,
        headers={"Content-Type":"application/json"} if body is not None else {},
        method="POST" if body is not None else "GET")
    started=time.monotonic()
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            return response.status,json.loads(response.read()),round(time.monotonic()-started,3)
    except urllib.error.HTTPError as error:
        return error.code,json.loads(error.read()),round(time.monotonic()-started,3)


def full(text):
    return {"q":text,"source":"en","target":TARGET}


def main():
    must(TARGET in ("ar","zh"),"This runner only tests Arabic and Chinese")
    must(metric("memory.max")==512*MiB,"Requires enforced 512MiB cap")
    before=events()
    OUT.mkdir(parents=True,exist_ok=True)
    report={"test":"R116-real-guarded-Gunicorn-HTTP-512MiB",
            "target":TARGET,"status":"NOT_COMPLETE",
            "human_approved":0,"production_writes":0,
            "netlify_deploys":0,"synthetic_only":True,
            "translation_quality_reviewed":False,
            "cache_enabled":False,"network_runtime":"disabled",
            "protected_segments_shielded":True}
    env=os.environ.copy()
    env.update({"FFH_GUARDED_API_STAGING_ONLY":"true",
                "FFH_TRANSLATION_CACHE_ENABLED":"false",
                "FFH_MULTILINGUAL":"false"})
    with (OUT/"gunicorn.log").open("w",encoding="utf-8") as logfile:
        proc=subprocess.Popen([
            sys.executable,"-m","gunicorn",
            "--workers","1","--threads","2","--timeout","120",
            "--bind","127.0.0.1:18761","app:app",
        ],env=env,stdout=logfile,stderr=subprocess.STDOUT)
        try:
            begin=time.monotonic()
            while time.monotonic()-begin<30:
                must(proc.poll() is None,"Gunicorn exited during startup")
                try:
                    response,body,_=http("/health",timeout=2)
                    if response==200 and body.get("status")=="ok":
                        break
                except (OSError,ValueError):
                    time.sleep(.1)
            else:
                raise RuntimeError("Health did not start within 30 seconds")
            report["health_start_seconds"]=round(time.monotonic()-begin,3)
            base,existing,_=http("/translate",full("A blue notebook."))
            must(base==200 and bool(existing.get("translatedText")),
                 "Legacy translate route regression")
            req=[
                {"id":"p1","q":"The note {{SAMPLE_ID}} belongs to page 17."},
                {"id":"p2","q":"The record {{ONE}} and {{TWO}} is in the library."},
                {"id":"p3","q":"The imaginary library contains a small box."},
                {"id":"n1","q":"Write 25 g on the imaginary paper card."},
                {"id":"n2","q":"A drawing has 8 flowers and 2 birds."},
                {"id":"url","q":"Visit https://example.invalid/test"},
                {"id":"email","q":"Contact demo@example.invalid"},
                {"id":"bad","q":"The note {{invalid}} is on the desk."},
                {"id":"p4","q":"Look at page 120 of the notebook."},
                {"id":"p5","q":"These are invented test sentences."}
            ]
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                pending=pool.submit(http,BATCH,{"source":"en","target":TARGET,
                                                "items":req},110)
                time.sleep(.04)
                report["health_probe_during_batch"]=not pending.done()
                hc,health,seconds=http("/health",timeout=6)
                report["health_during_batch"]={"code":hc,"seconds":seconds}
                code,body,batch_seconds=pending.result(timeout=115)
            must(code==200 and body.get("count")==len(req),
                 "Guarded batch did not return 10 results")
            must([r["id"] for r in body["results"]]==[r["id"] for r in req],
                 "Changed response order or IDs")
            must(body["human_approved"] is False,"Invalid review flag")
            must(report["health_probe_during_batch"] and hc==200 and seconds<5,
                 "Health did not respond during active translation")
            states={}
            held_reasons={}
            for row in body["results"]:
                must(row["human_approved"] is False and row["production_writes"]==0,
                     "Implicit review or production write detected")
                must(row["status"] in ("held","provisional_candidate"),
                     "Invalid result state")
                if row["status"]=="held":
                    must(row["draft"] is None,"Held result leaked a draft")
                    for r in row["reasons"]:
                        held_reasons[r]=held_reasons.get(r,0)+1
                else:
                    must(isinstance(row["draft"],str) and bool(row["draft"].strip()),
                         "Empty provisional candidate")
                states[row["id"]]=row["status"]
            must(states["p1"]=="provisional_candidate" and
                 states["p2"]=="provisional_candidate",
                 "Protected markers were not preserved")
            must(states["url"]=="held" and states["email"]=="held"
                 and states["bad"]=="held","Unsafe string entered translator")
            must(http(SINGLE,full("https://example.invalid/"))[1]["status"]=="held",
                 "Unprotected URLs must be held")
            must(http(SINGLE,full("{{invalid}}"))[1]["draft"] is None,
                 "Malformed protected marker leaked")
            must(http(BATCH,{"source":"en","target":TARGET,
                             "items":["sample"]*26})[0]==400,
                 "Existing 25-input limit violated")
            report["statuses"]=states
            report["reasons_counts"]=held_reasons
            report["guarded_batch_seconds"]=batch_seconds
            report["guarded_accepted_as_provisional"]=sum(
                v=="provisional_candidate" for v in states.values())
            report["guarded_held"]=sum(v=="held" for v in states.values())
            report["legacy_route_passed"]=True
            report["health_after_batch_status"]=http("/health")[0]
            must(report["health_after_batch_status"]==200,"Health failed post-batch")
            report["status"]="PASS_STAGING_RESOURCE_AND_INTEGRITY_ONLY"
        except Exception as error:
            report["status"]="FAIL"
            report["error_kind"]=type(error).__name__
            report["error_detail"]=str(error)[:400]
            raise
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            report["gunicorn_exit"]=proc.returncode
            report["peak_cgroup_mib"]=round(metric("memory.peak")/MiB,2)
            report["headroom_pct"]=round(
                (512-report["peak_cgroup_mib"])/512*100,2)
            after=events()
            report["oom_kills"]=after.get("oom_kill",0)-before.get("oom_kill",0)
            report["elapsed_seconds"]=round(time.monotonic()-START,2)
            (OUT/"summary.json").write_text(
                json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
            print("R116_GUNICORN_RESULT",json.dumps(report,sort_keys=True),flush=True)
    must(report["headroom_pct"]>=15,"Memory headroom less than 15%")
    must(report["oom_kills"]==0,"OOM kill observed")


if __name__=="__main__":
    main()
