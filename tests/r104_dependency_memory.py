"""R104 experimental dependency removal; test harness only. Never use for FFH production."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import resource
import sys
import time
from pathlib import Path

SENTENCES = [
    "The red notebook is on the table.",
    "There are 4 empty jars on the shelf.",
    "Write the date on the clean label.",
    "Sample 12 is a test record.",
    "These words are fictional.",
    "A wooden spoon is beside the bowl.",
    "Page 7 includes the list of examples.",
    "The small kitchen has a blue door.",
    "First open the notebook. Then turn to page 3.",
    "The children are reading. The teacher is writing.",
    "We are measuring 15 g of salt for this demonstration.",
    "Use 20 mL of water for the mock experiment.",
    "There are 10 numbered cards in this box.",
    "Look at chart 6 before continuing.",
    "The book belongs to the local library.",
    "This is only a software performance test.",
    "Read the short sentence aloud.",
    "The cup is half full of cold water.",
    "The afternoon meeting begins at 2.",
    "Our sample is not intended as food guidance.",
]
out = Path("r104-output")
NUM = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?")

def setup():
    import argostranslate.package as pkg
    pkg.update_package_index()
    model = next((x for x in pkg.get_available_packages()
                 if (x.from_code, x.to_code) == ("en", "es")), None)
    if model is None:
        raise RuntimeError("No direct en-es model")
    pkg.install_from_path(model.download())
    print("R104_MODEL", json.dumps({"version":str(model.package_version)}))

def child(worker, profile):
    from argostranslate import translate, settings
    begin = time.perf_counter()
    drafts = [translate.translate(x, "en", "es") for x in SENTENCES]
    elapsed = round(time.perf_counter() - begin, 3)
    flags=[]
    for i,(src,draft) in enumerate(zip(SENTENCES,drafts)):
        if not isinstance(draft,str) or not draft.strip():
            flags.append({"item":i,"reason":"empty"})
        if sorted(NUM.findall(src))!=sorted(NUM.findall(draft)):
            flags.append({"item":i,"reason":"number mismatch"})
    result={
        "worker":worker,"profile":profile,"count":len(drafts),
        "peak_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
        "translate_seconds":elapsed,
        "stanza_available":bool(importlib.util.find_spec("stanza")),
        "torch_available":bool(importlib.util.find_spec("torch")),
        "torch_loaded": "torch" in sys.modules,
        "chunk_type":str(settings.chunk_type),
        "compute_type":str(settings.compute_type),
        "drafts":drafts,"mechanical_flags":flags,
        "production_writes":0,"human_approved":0,"only_synthetic_data":True,
        "not_production_supported_install":True,
    }
    out.mkdir(parents=True,exist_ok=True)
    (out/f"{worker}-{profile}.json").write_text(
        json.dumps(result, ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("R104_PROFILE",json.dumps({
        k:v for k,v in result.items() if k!="drafts"
    },sort_keys=True),flush=True)
    assert len(drafts)==20

def compare(worker):
    a=json.loads((out/f"{worker}-full-deps.json").read_text(encoding="utf-8"))
    b=json.loads((out/f"{worker}-removed-optional.json").read_text(encoding="utf-8"))
    changes=[i for i,(left,right) in enumerate(zip(a["drafts"],b["drafts"])) if left!=right]
    report={
        "worker":worker,
        "original_peak_mib":a["peak_mib"],
        "experimental_peak_mib":b["peak_mib"],
        "memory_reduction_mib":round(a["peak_mib"]-b["peak_mib"],2),
        "below_512_mib":b["peak_mib"]<512,
        "below_400_mib":b["peak_mib"]<400,
        "translation_differences":changes,
        "original_flagged":a["mechanical_flags"],
        "modified_flagged":b["mechanical_flags"],
        "experimental_not_supported_deployment":True,
        "production_writes":0,
        "human_approved":0
    }
    (out/f"{worker}-comparison.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("R104_COMPARISON",json.dumps(report,sort_keys=True),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("task",choices=["setup","child","compare"])
    ap.add_argument("--worker",choices=["A","B"],default="A")
    ap.add_argument("--profile",default="full-deps")
    args=ap.parse_args()
    if args.task=="setup": setup()
    elif args.task=="child": child(args.worker,args.profile)
    else: compare(args.worker)
