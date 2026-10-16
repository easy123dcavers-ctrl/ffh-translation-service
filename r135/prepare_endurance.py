"""R135 full 30-minute nine-language conservative-memory experiment.

Only modify runtime inference profile (Argos batch=1 / beam=1 for all targets)
and one backend thread, preserving the independently validated R132
singleflight gateway, 10% exact cgroup RAM gate, 0.1 CPU, 1800s,
two complete language circuits and deliberate SIGKILL/UNKNOWN check.

Never production-deploy; machine translations remain provisional.
"""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
import sys
from r129.prepare_endurance import BASE_GIT_BLOB_SHA, replace_once
from r132.prepare_endurance import build as build_r132

def build(source: str) -> str:
    s=build_r132(source)
    s=replace_once(s,
        '''CONFIG={"es":(1,4),"fr":(8,4),"ko":(1,2),"vi":(1,2),
        "ja":(8,4),"de":(1,2),"ar":(8,4),"tl":(1,4),"zh":(8,4)}''',
        '''CONFIG={"es":(1,1),"fr":(1,1),"ko":(1,1),"vi":(1,1),
        "ja":(1,1),"de":(1,1),"ar":(1,1),"tl":(1,1),"zh":(1,1)}''')
    s=replace_once(s,
        '"--workers","1","--threads","2","--timeout","120"',
        '"--workers","1","--threads","1","--timeout","120"')
    s=replace_once(s,
        '"r132_singleflight":True,',
        '"r132_singleflight":True,"r135_conservative_inference":True,')
    ast.parse(s)
    return s

def main(argv):
    if len(argv)!=3:
        print("Usage: python -m r135.prepare_endurance PINNED_R125F_SOURCE OUTPUT",file=sys.stderr)
        return 2
    raw=Path(argv[1]).read_bytes()
    actual=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
    if actual != BASE_GIT_BLOB_SHA:
        raise RuntimeError(f"Unknown pinned R125F Git blob {actual}; STOP")
    output=Path(argv[2]);output.parent.mkdir(parents=True,exist_ok=True)
    generated=build(raw.decode("utf-8"))
    output.write_text(generated,encoding="utf-8")
    print("R135_FULL_REAL_MODEL_GENERATED",
          {"source_blob":actual,"sha256":hashlib.sha256(generated.encode()).hexdigest(),
           "language_targets":9,"soak_seconds":1800,
           "memory_limit_mib":512,"headroom_min_percent":10,"cpu_max":0.1})
    return 0

if __name__=="__main__":raise SystemExit(main(sys.argv))
