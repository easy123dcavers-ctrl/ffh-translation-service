"""R133 owner-approved 10% gate, real nine-model DISK image, two target switches.

Uses exact R132 generator with only diagnostic duration/sequence and cgroup
telemetry additions. This is NOT 30-minute nine-language release validation.
Preserve failure details rather than defeating the strict memory gate.
"""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
import sys
from r129.prepare_endurance import BASE_GIT_BLOB_SHA, replace_once
from r132.prepare_endurance import build as r132_build

def build(source: str) -> str:
    s = r132_build(source)
    s = replace_once(s,
        'SOAK_SECONDS=1800',
        'SOAK_SECONDS=90')
    s = replace_once(s,
        'SEQUENCE=("es","ko","fr","vi","ja","de","ar","tl","zh")',
        'SEQUENCE=("es","ko")')
    s = replace_once(s,
        'def http(url,path,payload=None,token=TOKEN,timeout=95):',
        '''def memory_components():
    values = {}
    for line in (Path("/sys/fs/cgroup")/"memory.stat").read_text().splitlines():
        parts = line.split()
        if len(parts)==2 and parts[1].isdecimal():
            values[parts[0]] = int(parts[1])
    keys=("anon","file","kernel","slab","shmem","pagetables",
          "kernel_stack","sock","file_mapped","inactive_file","active_file")
    return {
        "memory_current_mib": round(cgroup("memory.current")/MIB,3),
        "memory_peak_mib": round(cgroup("memory.peak")/MIB,3),
        "segments_mib": {k: round(values.get(k,0)/MIB,3) for k in keys},
    }

def http(url,path,payload=None,token=TOKEN,timeout=95):''')
    s = replace_once(s,
        '            try:\n                start=time.monotonic()',
        '''            round_info["memory_before_startup"]=memory_components()
            try:
                start=time.monotonic()''')
    s = replace_once(s,
        '                state.resume()',
        '''                round_info["memory_after_backend_health"]=memory_components()
                state.resume()''')
    s = replace_once(s,
        '                    observed_peak=cgroup("memory.peak")',
        '''                    round_info["memory_after_last_batch"]=memory_components()
                    observed_peak=cgroup("memory.peak")''')
    s = replace_once(s,
        '                round_info["current_mib_after_stop"]=round(cgroup("memory.current")/MIB,2)',
        '''                round_info["current_mib_after_stop"]=round(cgroup("memory.current")/MIB,2)
                round_info["memory_after_exit"]=memory_components()''')
    s = replace_once(s,
        '        report["memory_peak_mib"]=round(peak/MIB,2)',
        '''        report["memory_final_components"]=memory_components()
        report["r133_diagnostic_only"]=True
        report["memory_peak_mib"]=round(peak/MIB,2)''')
    ast.parse(s)
    return s

def main(argv):
    if len(argv)!=3:
        print('python -m r133.prepare_diagnostic BASE_TEST OUT',file=sys.stderr)
        return 2
    raw=Path(argv[1]).read_bytes()
    sha=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
    if sha != BASE_GIT_BLOB_SHA:
        raise RuntimeError(f"Source digest mismatch {sha}: halt")
    output=Path(argv[2]); output.parent.mkdir(parents=True,exist_ok=True)
    code=build(raw.decode("utf-8"))
    output.write_text(code,encoding="utf-8")
    print("R133_DIAGNOSTIC_ONLY","source",sha,
          "generated_sha256",hashlib.sha256(code.encode()).hexdigest())
    return 0

if __name__=="__main__":
    raise SystemExit(main(sys.argv))
