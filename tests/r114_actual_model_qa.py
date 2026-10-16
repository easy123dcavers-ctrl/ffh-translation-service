"""R114 real Argos + guarded candidate smoke, Arabic/Chinese only, synthetic."""
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path("/srv/ffh")
sys.path.insert(0,str(ROOT))
os.environ["ARGOS_PACKAGES_DIR"]=str(ROOT/".argos"/"packages")
TARGET=os.getenv("FFH_TARGET_LANGUAGE","")
if TARGET not in ("ar","zh"):
    raise RuntimeError("Only ar or zh models are approved for isolated R114 smoke")
from protected_translation import guarded_candidate
import app
from pathlib import Path

def cgroup_num(name):
    text=(Path("/sys/fs/cgroup")/name).read_text().strip()
    if not text.isdigit():
        raise RuntimeError("Unbounded memory group")
    return int(text)

def main():
    t0=time.perf_counter()
    if cgroup_num("memory.max") != 512*1024*1024:
        raise RuntimeError("Must run in 512MiB cgroup")
    test_inputs=[
        "The note {{SAMPLE_ID}} belongs to page 17.",
        "Please write 25 g on the invented sample card.",
        "The toy library record is marked {{ONE}} and {{TWO}}.",
        "The painted box contains 8 flowers and 2 birds.",
    ]
    rows=[]
    for source in test_inputs:
        x=guarded_candidate(source,lambda t:app.translate_text(t,TARGET))
        assert x["human_approved"] is False and x["production_writes"]==0
        if "{{" in source:
            assert x["protected_placeholders"] in (1,2)
            assert "placeholder_integrity" not in x["reasons"]
        rows.append({
            "protected":x["protected_placeholders"],
            "status":x["status"],
            "reasons":x["reasons"],
            "draft_available": x["draft"] is not None
        })
    report={
        "test":"R114-real-low-memory-protected-candidate-smoke",
        "language":TARGET,
        "cases":rows,
        "held":sum(x["status"]=="held" for x in rows),
        "provisional_only":True,
        "approved":0,
        "production_writes":0,
        "memory_peak_mib":round(cgroup_num("memory.peak")/1024**2,2),
        "memory_limit_mib":512,
        "elapsed_seconds":round(time.perf_counter()-t0,2),
    }
    out=Path("/srv/ffh/r114-output")
    out.mkdir(parents=True,exist_ok=True)
    (out/"summary.json").write_text(json.dumps(report,indent=2)+"\n")
    print("R114_REAL_RESULT",json.dumps(report,sort_keys=True),flush=True)
    if report["memory_peak_mib"] >= 512*0.85:
        raise RuntimeError("No 15% memory safety margin")

if __name__=="__main__":
    main()
