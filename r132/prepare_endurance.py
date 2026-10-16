"""R132 disposable 30min test generation from pinned baseline R131.

R125 gateway in this experiment has atomic admission (busy returns 429),
unlike older R131 which delegated the 429 to the backend. This generator
only changes the test's unreliable sleep-based batch-start race detector.
"""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
import sys
from r129.prepare_endurance import BASE_GIT_BLOB_SHA, replace_once
from r131.prepare_endurance import build as build_r131

def build(source: str) -> str:
    s=build_r131(source)
    old='''                        time.sleep(.085)
                        ensure(not pending.done(),
                            "Concurrent batch completed before 429 challenge")'''
    new='''                        # Observe actual gateway admission before a busy probe.
                        # No arbitrary fixed sleep; the concurrency tests separately
                        # prove atomic single-flight with a deliberately blocked backend.
                        for _attempt in range(500):
                            if state.snapshot()["active"] == 1:
                                break
                            ensure(not pending.done(),
                                   "Batch finished before gateway admission evidence")
                            time.sleep(.005)
                        ensure(state.snapshot()["active"] == 1,
                               "Busy probe: batch was not admitted")
                        ensure(not pending.done(),
                               "Batch finished before competing request")'''
    s=replace_once(s,old,new)
    s=replace_once(s,
        '"build_time_all_nine_tree_sha_verified":True,',
        '"build_time_all_nine_tree_sha_verified":True,"r132_singleflight":True,')
    ast.parse(s)
    return s

def main(argv):
    if len(argv)!=3:
        print("python -m r132.prepare_endurance PINNED_SOURCE GENERATED_DEST",file=sys.stderr)
        return 2
    original=Path(argv[1]).read_bytes()
    blob=hashlib.sha1(f"blob {len(original)}\0".encode()+original).hexdigest()
    if blob!=BASE_GIT_BLOB_SHA:
        raise RuntimeError(f"R132 source blob changed: {blob}; STOP")
    s=build(original.decode("utf-8"))
    output=Path(argv[2]);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(s,encoding="utf-8")
    print("R132 generated",hashlib.sha256(s.encode()).hexdigest())
    return 0

if __name__=="__main__":
    raise SystemExit(main(sys.argv))
