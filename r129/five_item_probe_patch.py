"""R129 REAL model five-item diagnostic; never production."""
from __future__ import annotations
import ast
import hashlib
import pathlib
import sys

BASE_GIT_BLOB_SHA='a73832312115cc02c019cb1fa2e8edd457c7654b'
PATCHES=(
    ('for i in range(23)', 'for i in range(3)'),
    ('base+23', 'base+3'),
    ('base+24', 'base+4'),
    ('payload.get("count")==25', 'payload.get("count")==5'),
    ('len(rows)==25', 'len(rows)==5'),
    ('round_info["items"]+=25', 'round_info["items"]+=5'),
    ('report["items"]+=25', 'report["items"]+=5'),
    ('report["items"]==report["busy_429"]*25', 'report["items"]==report["busy_429"]*5'),
)

def patch(source: str) -> str:
    for old,new in PATCHES:
        if source.count(old)!=1:
            raise RuntimeError(f'Noncanonical R125f test: expected one {old!r}, got {source.count(old)}')
        source=source.replace(old,new,1)
    ast.parse(source)
    return source

def main(argv):
    if len(argv)!=3:
        print('Usage: python -m r129.five_item_probe_patch SOURCE OUT',file=sys.stderr)
        return 2
    src=pathlib.Path(argv[1]);out=pathlib.Path(argv[2])
    original=src.read_bytes()
    sha=hashlib.sha1(f'blob {len(original)}\0'.encode()+original).hexdigest()
    if sha!=BASE_GIT_BLOB_SHA:
        raise RuntimeError(f'Base SHA mismatch; refused: {sha}')
    data=patch(original.decode('utf-8'))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(data)
    print('R129 5-item diagnostic generated from known R125F SHA; NOT 30-minute pass')
    return 0

if __name__=='__main__':raise SystemExit(main(sys.argv))
