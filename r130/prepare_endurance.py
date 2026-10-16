"""Generate R130 full-scale disposable nine-language 10%-reserve endurance.

Reuses R129 strict source pinning, 30-minute scheduling and SIGKILL witness;
changes ONLY the owner-authorized headroom acceptance policy and its manifest
label. Never deploy this to Render; stage requires real Member broker later.
"""
from __future__ import annotations
import ast
import hashlib
from pathlib import Path
import sys
from r129.prepare_endurance import BASE_GIT_BLOB_SHA, prepare, replace_once

def build(source: str) -> str:
    result = prepare(source)
    result = replace_once(result,
        'from r123h_memory_policy import memory_gate',
        'from r130_memory_policy import memory_gate')
    result = replace_once(result,
        '"permitted_peak_mib":409.6,"headroom_min_pct":20',
        '"permitted_peak_mib":460.8,"headroom_min_pct":10')
    result = replace_once(result,
        '"R125F strict tripwire: 20% memory reserve breached during batch"',
        '"R130 strict tripwire: owner-approved 10% memory reserve breached during batch"')
    result = replace_once(result,
        '"R125 memory less than 20% headroom, or OOM kill"',
        '"R130 memory less than 10% headroom, or OOM kill"')
    ast.parse(result)
    return result

def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: python -m r130.prepare_endurance SOURCE OUT", file=sys.stderr)
        return 2
    original = Path(argv[1]).read_bytes()
    pin = hashlib.sha1(f"blob {len(original)}\0".encode() + original).hexdigest()
    if pin != BASE_GIT_BLOB_SHA:
        raise RuntimeError(f"Refuse unknown original R125F blob: {pin}")
    derived = build(original.decode("utf-8"))
    target = Path(argv[2])
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(derived,encoding="utf-8")
    print("R130_GENERATED", {"base_blob":pin,
        "derived_sha256":hashlib.sha256(derived.encode()).hexdigest(),
        "threshold":"10% exact cgroup, 512MiB, 0.1 CPU, 1800s minimum"})
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
