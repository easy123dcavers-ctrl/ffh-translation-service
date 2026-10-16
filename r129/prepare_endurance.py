"""R129 disposable-only generator from verified R125F real-model runner.
Fail closed on upstream edits. Never deploy this generated runner.
"""
from __future__ import annotations
import ast
import hashlib
import pathlib
import sys

BASE_GIT_BLOB_SHA = "a73832312115cc02c019cb1fa2e8edd457c7654b"

def replace_once(source: str, before: str, after: str) -> str:
    count = source.count(before)
    if count != 1:
        raise ValueError(f"R129 source changed: anchor count {count}, expected 1: {before[:90]!r}")
    return source.replace(before, after, 1)

def prepare(original: str) -> str:
    s = original
    s = replace_once(s, 'import concurrent.futures\n',
                     'import concurrent.futures\nimport itertools\nimport signal\n')
    s = replace_once(s, 'SOAK_SECONDS=252', 'SOAK_SECONDS=1800')
    s = replace_once(s, '    ensure(cgroup("memory.max")==LIMIT,"Require enforced 512MiB cgroup")',
        '''    ensure(cgroup("memory.max")==LIMIT,"Require enforced 512MiB cgroup")
    cpu_max=(Path("/sys/fs/cgroup")/"cpu.max").read_text().split()
    ensure(len(cpu_max)==2 and all(x.isdecimal() for x in cpu_max),
           "Require hard CPU quota with finite numerator and period")
    ensure(int(cpu_max[0])*10 <= int(cpu_max[1]),
           "CPU quota must be <=0.1 core")''')
    s = replace_once(s, '            "rounds":[],"items":0,',
        '''            "cpu_max":" ".join(cpu_max),"requested_soak_seconds":SOAK_SECONDS,
            "sigkill_unknown_verified":0,"rounds":[],"items":0,''')
    s = replace_once(s, '        for index,target in enumerate(SEQUENCE):',
        '''        for index,target in enumerate(itertools.cycle(SEQUENCE)):
            if index >= len(SEQUENCE)*2 and time.monotonic() >= end:
                break''')
    s = replace_once(s, '                cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT)',
        '                cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT,\n                start_new_session=True)')
    s = replace_once(s, '                # Set gateway UNAVAILABLE before waiting for in-flight clients.',
        '''                # One real in-flight backend SIGKILL after >=2 circuits and >=30min.
                # Outcome must be UNKNOWN, never silently retried.
                if index >= len(SEQUENCE)*2 and time.monotonic() >= end:
                    crash_data={"source":"en","target":target,
                                "items":items(target,index*100+999)}
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                        in_flight=ex.submit(http,url,
                            "/experimental/guarded-translate-batch",
                            crash_data,TOKEN,110)
                        for _ in range(200):
                            if state.snapshot()["active"] == 1:
                                break
                            ensure(not in_flight.done(),
                                   "Crash sample completed before gateway admission")
                            time.sleep(.01)
                        ensure(state.snapshot()["active"]==1,
                               "Crash sample never admitted")
                        ensure(not in_flight.done(),
                               "Crash sample completed before kill")
                        os.killpg(proc.pid, signal.SIGKILL)
                        crash_status,crash_body,_,_=in_flight.result(timeout=30)
                    ensure(crash_status==502 and
                           crash_body.get("error")=="translation outcome unknown" and
                           crash_body.get("retryable") is False,
                           "In-flight SIGKILL did not report 502 UNKNOWN")
                    round_info["intentional_sigkill"]=True
                    report["sigkill_unknown_verified"]+=1
                # Set gateway UNAVAILABLE before waiting for in-flight clients.''')
    s = replace_once(s,
        '            ensure(round_info["exit_code"]==0 and\n                   round_info["worker_boots"]==1 and',
        '''            ensure((round_info["exit_code"]==0 or
                    (round_info.get("intentional_sigkill") is True and
                     round_info["exit_code"] == -signal.SIGKILL)) and
                   round_info["worker_boots"]==1 and''')
    s = replace_once(s,
        '        ensure(len(report["rounds"])==len(SEQUENCE) and\n               len({x["master_pid"] for x in report["rounds"]})==len(SEQUENCE),\n               "Expected four separate model processes")',
        '''        ensure(len(report["rounds"])>=2*len(SEQUENCE) and
               len({x["master_pid"] for x in report["rounds"]})==len(report["rounds"]),
               "Need >=2 circuits with separate backend processes")
        ensure(time.monotonic()-START>=SOAK_SECONDS,
               "Real monotonic soak shorter than 1800 seconds")
        ensure(sum(r["target"]=="de" for r in report["rounds"])>=2,
               "German must be revisited across circuits")
        ensure(report["sigkill_unknown_verified"]==1,
               "Require exactly one real SIGKILL/unknown witness")''')
    s = replace_once(s,
        '        report["wall_seconds"]=round(time.monotonic()-START,2)',
        '''        report["wall_seconds"]=round(time.monotonic()-START,2)
        report["completed_circuits"]=len(report["rounds"])//len(SEQUENCE)
        if report["wall_seconds"]<SOAK_SECONDS:
            report["status"]="HOLD_DURATION"''')
    ast.parse(s)
    return s

def main(argv: list[str]) -> int:
    if len(argv)!=3:
        print("Usage: python -m r129.prepare_endurance SOURCE OUT",file=sys.stderr)
        return 2
    source=pathlib.Path(argv[1]); target=pathlib.Path(argv[2])
    original=source.read_text(encoding="utf-8")
    raw=original.encode("utf-8")
    blob=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
    if blob != BASE_GIT_BLOB_SHA:
        raise RuntimeError(f"Unknown R125F base Git blob: {blob}; STOP")
    transformed=prepare(original)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(transformed,encoding="utf-8")
    print(f"R129 GENERATED_FROM_GIT_BLOB={blob} OUTPUT_SHA256={hashlib.sha256(transformed.encode()).hexdigest()}")
    return 0

if __name__=='__main__':
    raise SystemExit(main(sys.argv))
