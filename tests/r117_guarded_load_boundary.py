"""R117 isolated guarded API load boundary probe. NO production calls or approvals.

One model/container, 512 MiB cgroup, 1 CPU, 1 Gunicorn worker / 2 threads.
Two full 25-item batches across two server startups, plus parallel small
batches, near-limit text, health checks and strict fail-closed integrity.
The output is a RESOURCE/HTTP benchmark, not a linguistic review.
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

TARGET=os.environ.get("FFH_TARGET_LANGUAGE", "")
ROOT=Path("/srv/ffh")
OUT=ROOT/"r117-output"
URL="http://127.0.0.1:18771"
MIB=1024*1024
START=time.monotonic()
ALL_TARGETS={"es","fr","de","ja","ar","tl","ko","vi","zh"}

def require(check,message):
    if not check: raise RuntimeError(message)

def cgroup_num(name):
    p=Path("/sys/fs/cgroup")/name
    require(p.is_file(), "Missing memory cgroup metric "+name)
    value=p.read_text().strip()
    require(value.isdecimal(),"Missing 512MiB memory cap")
    return int(value)

def memory_events():
    path=Path("/sys/fs/cgroup/memory.events")
    return {x.split()[0]:int(x.split()[1]) for x in path.read_text().splitlines()}

def request(path, payload=None, timeout=120):
    encoded=None if payload is None else json.dumps(payload).encode()
    query=urllib.request.Request(URL+path, data=encoded,
        method="POST" if encoded is not None else "GET",
        headers={"Content-Type":"application/json"} if encoded is not None else {})
    t0=time.monotonic()
    try:
        with urllib.request.urlopen(query, timeout=timeout) as stream:
            return (stream.status, json.loads(stream.read()),
                    round(time.monotonic()-t0,3))
    except urllib.error.HTTPError as err:
        return (err.code, json.loads(err.read()),
                round(time.monotonic()-t0,3))

def payload(inputs):
    return {"items":inputs,"source":"en","target":TARGET}

def checked_batch(data, expected_ids, report):
    require(data[0]==200,"Non-200 guarded batch response")
    obj=data[1]
    require(obj.get("count")==len(expected_ids), "Incorrect batch count")
    require(obj.get("human_approved") is False, "Review bypass at batch level")
    rows=obj.get("results",[])
    require([x.get("id") for x in rows]==expected_ids, "Batch id/order mismatch")
    counts={"held":0,"provisional_candidate":0}
    holds={}
    for row in rows:
        state=row.get("status")
        require(state in counts,"Unexpected candidate state")
        require(row.get("human_approved") is False and row.get("production_writes")==0,
                "Candidate bypassed review or production policy")
        require(row.get("draft") is None if state=="held" else
                isinstance(row.get("draft"),str) and bool(row.get("draft").strip()),
                "Held draft leakage or empty provisional output")
        counts[state]+=1
        for flag in row.get("reasons",[]):
            holds[flag]=holds.get(flag,0)+1
    report["items"]+=len(rows)
    report["provisional"]+=counts["provisional_candidate"]
    report["held"]+=counts["held"]
    for key,value in holds.items():
        report["reason_counts"][key]=report["reason_counts"].get(key,0)+value
    return obj

def expected_placeholders(rows,inputs):
    for row,inp in zip(rows["results"],inputs):
        marker=inp["q"]
        if "{{" in marker and "}}" in marker and "{{invalid}}" not in marker:
            # No draft may be returned unless the exact token is restored.
            if row["status"]=="provisional_candidate":
                for token in ("{{BATCH_ID}}","{{ROW_ID}}"):
                    if token in marker:
                        require(token in row["draft"], "Protected placeholder lost")

def make_items(round_no):
    items=[]
    for i in range(20):
        n=round_no*100+i+1
        s=f"Record {n} is on the blue library shelf. There are {n+3} blank pages in the notebook."
        items.append({"id":f"plain-{round_no}-{i}","q":s})
    items+= [
        {"id":f"p1-{round_no}","q":"The note {{BATCH_ID}} is on the table."},
        {"id":f"p2-{round_no}","q":"The card {{ROW_ID}} is beside the book."},
        {"id":f"bad-{round_no}","q":"The note {{invalid}} is empty."},
        {"id":f"url-{round_no}","q":"Open https://example.invalid/test"},
        {"id":f"limit-{round_no}","q":"Z"*4097},
    ]
    require(len(items)==25,"Incorrect 25-item fixture")
    return items

def concurrent_set(round_no):
    groups=[]
    for group in range(2):
        items=[]
        for i in range(4):
            items.append({"id":f"c{round_no}-{group}-{i}",
                          "q":f"The imaginary reading room has {i+11} blue chairs."})
        items += [{"id":f"c{round_no}-{group}-placeholder",
                   "q":"The sample {{ROW_ID}} is a fictional card."},
                  {"id":f"c{round_no}-{group}-measure",
                   "q":"A painting uses 25 g of colored paper."}]
        groups.append(items)
    return groups

def long_source(round_no):
    short=("The imaginary library has an east wing with blue doors. "
           "A researcher wrote a fictional story about a small notebook. "
           "Visitors see chairs, books, maps, and paintings. "
           "The description is intended only for a software stress test. ")
    return f"Fictional long entry {round_no}.\n\n"+short*11

def run_round(round_no):
    log=(OUT/f"server-{round_no}.log").open("w",encoding="utf-8")
    env=dict(os.environ)
    env.update({"FFH_GUARDED_API_STAGING_ONLY":"true",
                "FFH_TRANSLATION_CACHE_ENABLED":"false",
                "FFH_MULTILINGUAL":"false"})
    proc=subprocess.Popen([sys.executable,"-m","gunicorn",
        "--workers","1","--threads","2","--timeout","120",
        "--bind","127.0.0.1:18771","app:app"],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    record={"round":round_no,"pid":proc.pid,"items":0,"held":0,"provisional":0,
            "reason_counts":{},"health_checks":[],"concurrent_batch_seconds":[],
            "server_exit":None}
    try:
        t=time.monotonic()
        while time.monotonic()-t<40:
            require(proc.poll() is None,"Server stopped while starting")
            try:
                if request("/health",timeout=1.5)[0]==200:break
            except (OSError, ValueError):
                time.sleep(.1)
        else:
            raise RuntimeError("Server startup/health timeout")
        record["startup_seconds"]=round(time.monotonic()-t,3)
        require(request("/")[1].get("configured_target")==TARGET,"Wrong target")
        items=make_items(round_no)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(request,"/experimental/guarded-translate-batch",payload(items),115)
            time.sleep(.05)
            require(not future.done(),"25-item batch ended before health measurement")
            health=request("/health",timeout=5)
            record["health_checks"].append({"mode":"during_25","status":health[0],
                                            "seconds":health[2]})
            result=future.result(timeout=120)
        checked=checked_batch(result,[x["id"] for x in items],record)
        expected_placeholders(checked,items)
        require(record["reason_counts"].get("malformed_placeholder",0)>=1,
                "Malformed placeholder was not held")
        require(record["reason_counts"].get("unprotected_url_or_email",0)>=1,
                "URL was not held")
        require(record["reason_counts"].get("source_too_long",0)>=1,
                "Oversized source was not held")
        record["full_batch_seconds"]=result[2]
        groups=concurrent_set(round_no)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(request,"/experimental/guarded-translate-batch",
                    payload(group),115) for group in groups]
            time.sleep(.04)
            record["both_concurrent_batches_active"]=all(not x.done() for x in futures)
            health_error=None
            try:
                health=request("/health",timeout=5)
                record["health_checks"].append({"mode":"two_parallel_batches",
                    "status":health[0],"seconds":health[2]})
            except Exception as e:
                health_error=type(e).__name__
                record["health_checks"].append({"mode":"two_parallel_batches",
                    "status":0,"error":health_error,"seconds":5})
            outputs=[f.result(timeout=120) for f in futures]
        for output, group in zip(outputs,groups):
            obj=checked_batch(output,[x["id"] for x in group],record)
            expected_placeholders(obj,group)
            record["concurrent_batch_seconds"].append(output[2])
        longtext=long_source(round_no)
        require(2000<=len(longtext)<=4096,"Long fixture not within 2–4 KB limit")
        result=request("/experimental/guarded-translate",{
            "q":longtext,"source":"en","target":TARGET},115)
        require(result[0]==200, "Long-source HTTP failed")
        require(result[1].get("status") in ("held","provisional_candidate"),
                "Long-source returned invalid state")
        require(result[1].get("human_approved") is False, "Long-source self-approved")
        if result[1]["status"]=="held":
            require(result[1]["draft"] is None,"Long-source held result leaked")
        record["long_source"]={"chars":len(longtext),"seconds":result[2],
            "status":result[1]["status"],"reasons":result[1]["reasons"]}
        record["health_after"]=request("/health",timeout=5)[0]
        require(record["health_after"]==200,"Health failed after work")
        for h in record["health_checks"]:
            require(h.get("status")==200 and h.get("seconds",99)<5,
                    f"Health check not responsive: {h}")
        require(record["both_concurrent_batches_active"],
                "Parallel translation did not overlap for this trial")
        return record
    finally:
        if proc.poll() is None:proc.terminate()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        record["server_exit"]=proc.returncode
        log.close()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    require(TARGET in ALL_TARGETS,"Unknown target or profile")
    require(cgroup_num("memory.max")==512*MIB,
            "R117 requires real 512 MiB Docker memory cgroup")
    initial=memory_events()
    result={"test":"R117-nine-language-guarded-load-boundary",
        "target":TARGET,"status":"NOT_STARTED",
        "experimental_only":True,"human_approved":0,"production_writes":0,
        "no_runtime_network":True,"cache_enabled":False,
        "linguistic_accuracy_tested":False,"rounds":[],
        "cgroup_limit_mib":512,
        "profile":{"argos_batch":os.getenv("ARGOS_BATCH_SIZE"),
                   "argos_beam":os.getenv("ARGOS_BEAM_SIZE","default")}}
    try:
        for i in range(2):
            result["rounds"].append(run_round(i))
            print("R117_ROUND",json.dumps(result["rounds"][-1],sort_keys=True),flush=True)
        require(result["rounds"][0]["pid"]!=result["rounds"][1]["pid"],
                "No server restart was observed")
        result["status"]="PASS_ALL_INTEGRITY_HTTP_STRESS_GATES"
    except Exception as exc:
        result["status"]="HOLD_FAILED_TEST"
        result["failure_type"]=type(exc).__name__
        result["failure_detail"]=str(exc)[:300]
        raise
    finally:
        peak=cgroup_num("memory.peak")/MIB
        result["cgroup_peak_mib"]=round(peak,2)
        result["headroom_pct"]=round((512-peak)/512*100,2)
        after=memory_events()
        result["oom_kills"]=after.get("oom_kill",0)-initial.get("oom_kill",0)
        result["elapsed_seconds"]=round(time.monotonic()-START,2)
        # The final status MUST account for ALL exit gates, not only HTTP.
        if result["oom_kills"]>0 or result["headroom_pct"]<15:
            result["status"]="HOLD_MEMORY_GATE"
        (OUT/"summary.json").write_text(
            json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n",
            encoding="utf-8")
        print("R117_RESULT",json.dumps({k:v for k,v in result.items()
            if k!="rounds"},sort_keys=True),flush=True)
    require(result["oom_kills"]==0,"OOM killed container")
    require(result["headroom_pct"]>=15,"Insufficient 15% memory headroom")

if __name__=="__main__":
    main()
