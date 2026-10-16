"""R134 resource diagnostic. Two real models, conservative inference + exact RAM gate.

Derives from pinned R125F through R133 without altering production.
Changes CTranslate2 batch=1/beam=1, Gunicorn one model thread, and corrects
the inherited nine-language German check for a TWO-language diagnostic.
Build-time SHA of all nine model files remains mandatory. No approvals.
"""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
import sys
from r129.prepare_endurance import BASE_GIT_BLOB_SHA, replace_once
from r133.prepare_diagnostic import build as build_r133

def build(source: str) -> str:
    s=build_r133(source)
    original='''CONFIG={"es":(1,4),"fr":(8,4),"ko":(1,2),"vi":(1,2),
        "ja":(8,4),"de":(1,2),"ar":(8,4),"tl":(1,4),"zh":(8,4)}'''
    conservative='''CONFIG={"es":(1,1),"fr":(1,1),"ko":(1,1),"vi":(1,1),
        "ja":(1,1),"de":(1,1),"ar":(1,1),"tl":(1,1),"zh":(1,1)}'''
    s=replace_once(s,original,conservative)
    s=replace_once(s,'"--workers","1","--threads","2","--timeout","120"',
                      '"--workers","1","--threads","1","--timeout","120"')
    s=replace_once(s,
        '''        ensure(sum(r["target"]=="de" for r in report["rounds"])>=2,
               "German must be revisited across circuits")''',
        '''        ensure(sum(r["target"]=="es" for r in report["rounds"])>=2 and
               sum(r["target"]=="ko" for r in report["rounds"])>=2,
               "Both diagnostic targets must be revisited across circuits")''')
    s=replace_once(s,
        'report["r133_diagnostic_only"]=True',
        'report["r133_diagnostic_only"]=True; report["r134_conservative_inference"]=True')
    ast.parse(s)
    return s

def main(argv):
    if len(argv)!=3:
        print("Usage: python -m r134.prepare_probe PINNED_R125F_SOURCE OUTPUT",file=sys.stderr)
        return 2
    raw=Path(argv[1]).read_bytes()
    actual=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
    if actual != BASE_GIT_BLOB_SHA:
        raise RuntimeError(f"Unknown pinned source {actual}: STOP")
    out=Path(argv[2]);out.parent.mkdir(parents=True,exist_ok=True)
    code=build(raw.decode("utf-8"))
    out.write_text(code,encoding="utf-8")
    print("R134_DIAGNOSTIC_NOT_ENDURANCE",hashlib.sha256(code.encode()).hexdigest())
    return 0

if __name__=="__main__":raise SystemExit(main(sys.argv))
