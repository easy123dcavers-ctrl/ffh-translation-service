"""R119 model tree verifier: fail closed when installed files differ from R113 CI.

This compares *post-installation* tree bytes with an earlier known-good
R113 synthetic benchmark artifact. It DOES NOT validate the independent
upstream download archive, publisher signature, chain of custody or license.
"""
import hashlib
import json
import os
from pathlib import Path


def tree_digest(path):
    path = Path(path)
    if not path.is_dir():
        raise ValueError("Argos package directory missing")
    files = sorted(p for p in path.rglob("*") if p.is_file())
    if not files:
        raise ValueError("No installed Argos model files")
    h = hashlib.sha256()
    total = 0
    for f in files:
        file_hash = hashlib.sha256()
        with f.open("rb") as stream:
            while data := stream.read(1024 * 1024):
                file_hash.update(data)
                total += len(data)
        h.update(str(f.relative_to(path)).encode()+b"\0"+
                 file_hash.hexdigest().encode()+b"\n")
    return {"sha256":h.hexdigest(), "bytes":total, "files":len(files)}


def verify(target, model_dir, baselines):
    if not target or target not in baselines.get("verified_packages",{}):
        raise ValueError("Unknown or unpinned model target: stop")
    expected = baselines["verified_packages"][target]
    current = tree_digest(model_dir)
    if current["sha256"] != expected["sha256"] or current["bytes"] != expected["bytes"]:
        raise ValueError("Model tree differs from verified R113 baseline: stop")
    return {"target":target,"status":"same_files_as_R113_baseline",
            "tree_sha256":current["sha256"],"tree_bytes":current["bytes"],
            "tree_files":current["files"],"release_certified":False}


if __name__=="__main__":
    root=Path(__file__).resolve().parents[1]
    observed=json.loads((root/"models/r119_observed_model_trees.json").read_text())
    result=verify(os.environ.get("FFH_TARGET_LANGUAGE",""),
                  root/".argos"/"packages",observed)
    print("R119_MODEL_REPEATABILITY",json.dumps(result,sort_keys=True),flush=True)
