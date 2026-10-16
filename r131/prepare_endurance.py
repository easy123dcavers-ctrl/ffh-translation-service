"""R131 30-minute real-model staged endurance.

Generates from the exact pinned R125F file through the tested R130 10% owner
approval pipeline. Models are SHA-256 tree-verified when Docker builds, rather
than re-reading every model tree just before importing its Argos runtime.
No public broker, no production writes, no deployment. Requires CI evidence.
"""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
import sys
from r129.prepare_endurance import BASE_GIT_BLOB_SHA, replace_once
from r130.prepare_endurance import build as build_r130

def build(source: str) -> str:
    result=build_r130(source)
    old='    match=verify(target,p,baselines)'
    new='''    # R131 disposable: SHA-256 manifest validated at Docker BUILD for each
    # language (R119 verifier). Model files are image-internal, no runtime network.
    # Avoid re-reading >100MiB of files before loading every Argos model; under a
    # 512MiB cgroup that page-cache overlap was observed to exhaust RAM headroom.
    expected=baselines.get("verified_packages",{}).get(target)
    ensure(isinstance(expected,dict),"Unknown pinned model: stop")
    digest=expected.get("sha256")
    size=expected.get("bytes")
    ensure(isinstance(digest,str) and len(digest)==64 and
           all(x in "0123456789abcdef" for x in digest),
           "Invalid pinned model sha256")
    ensure(type(size) is int and size>0,"Invalid pinned model size")
    match={"target":target,"status":"build_verified_manifest_only",
           "tree_sha256":digest,"tree_bytes":size,
           "tree_files":expected.get("files",0),
           "release_certified":False}'''
    result=replace_once(result,old,new)
    result=replace_once(result,
        '"model_loading":"fresh single Gunicorn process per selected model",',
        '"model_loading":"fresh single Gunicorn process per selected model",\n            "per_switch_tree_rehash":False,"build_time_all_nine_tree_sha_verified":True,')
    ast.parse(result)
    return result

def main(argv: list[str]) -> int:
    if len(argv)!=3:
        print("Usage: python -m r131.prepare_endurance PINNED_R125F_SOURCE OUT",file=sys.stderr)
        return 2
    original=Path(argv[1]).read_bytes()
    digest=hashlib.sha1(f"blob {len(original)}\0".encode()+original).hexdigest()
    if digest != BASE_GIT_BLOB_SHA:
        raise RuntimeError(f"R131 REFUSES source blob change: {digest}")
    result=build(original.decode("utf-8"))
    target=Path(argv[2]);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(result,encoding="utf-8")
    print("R131_GENERATED",{"base_blob":digest,
        "sha256":hashlib.sha256(result.encode()).hexdigest(),
        "headroom_min":10,"cpu":0.1,"duration_seconds":1800,
        "model_tree_checks":"SHA at Docker build; no per-stage full hash"})
    return 0

if __name__=="__main__":
    raise SystemExit(main(sys.argv))
