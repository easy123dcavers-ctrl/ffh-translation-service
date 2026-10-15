"""FFH R100 isolated benchmark: only deterministic invented text, never FFH data."""
import argparse
import hashlib
import json
import re
import resource
import time
from pathlib import Path

TEMPLATES = (
    "Record sample {n} in the fermentation notebook.",
    "The clean jar marked {n} is on the lower shelf.",
    "Open page {n} of the recipe library.",
    "The mixture for sample {n} has a fresh aroma.",
    "Wash {n} clean glass jars before use.",
    "Read chapter {n} in the fermentation guide.",
    "The pantry contains {n} empty containers.",
    "Measure {n} g of sea salt for the experiment.",
    "Place {n} chopped carrots into the bowl.",
    "Use {n} small bowls for the experiment.",
)

def samples():
    return [{"id": t * 10 + number - 1, "source": template.format(n=number)}
            for t, template in enumerate(TEMPLATES) for number in range(1, 11)]

def numerals(s):
    return sorted(v.replace(',', '.') for v in re.findall(r'(?<![A-Za-z])\d+(?:[.,]\d+)?', s))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shard-index', type=int, choices=(0, 1), required=True)
    ap.add_argument('--target', choices=('es', 'fr', 'ja'), default='es')
    ap.add_argument('--output-dir', default='r100-output')
    args = ap.parse_args()
    import argostranslate.package as pkg
    import argostranslate.translate as tx
    all_samples = samples()
    assert len(all_samples) == 100 and len({x['source'] for x in all_samples}) == 100
    chosen = [s for s in all_samples if s['id'] % 2 == args.shard_index]
    assert len(chosen) == 50
    print('R100_SHARD', json.dumps({"shard": args.shard_index, "target": args.target,
                                   "count": len(chosen), "synthetic_only": True}))
    pkg.update_package_index()
    model = next((p for p in pkg.get_available_packages()
                  if p.from_code == 'en' and p.to_code == args.target), None)
    if model is None:
        raise RuntimeError('No direct Argos en-' + args.target + ' model; test cannot proceed')
    model_version = str(model.package_version)
    pkg.install_from_path(model.download())
    started = time.perf_counter()
    rows = []
    for item in chosen:
        t0 = time.perf_counter()
        flags = []
        try:
            draft = tx.translate(item['source'], 'en', args.target)
            if not isinstance(draft, str) or not draft.strip() or draft.strip() == item['source']:
                flags.append('empty_or_identical')
            if numerals(item['source']) != numerals(draft):
                flags.append('numeral_mismatch')
            ok = bool(draft.strip())
        except Exception as e:
            draft = ''
            ok = False
            flags.append('translation_exception_' + type(e).__name__)
        rows.append({"id": item['id'], "source": item['source'], "draft": draft,
                     "status": 'provisional_candidate' if ok and not flags else 'held',
                     "flags": flags, "seconds": round(time.perf_counter() - t0, 4)})
    elapsed = round(time.perf_counter() - started, 3)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = '\n'.join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + '\n'
    (out / 'synthetic_drafts.jsonl').write_text(payload, encoding='utf-8')
    held = sum(row['status'] == 'held' for row in rows)
    result = {
        "test": "R100-isolated-two-account-shard", "target": args.target,
        "shard_index": args.shard_index, "shard_count": 2,
        "sample_ids_sha256": hashlib.sha256(json.dumps([x['id'] for x in chosen]).encode()).hexdigest(),
        "model_version": model_version, "attempted": len(rows),
        "provisional_candidates": len(rows) - held, "held": held,
        "elapsed_seconds": elapsed, "seconds_per_item": round(elapsed / len(rows), 4),
        "peak_process_memory_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "human_approved": 0, "production_writes": 0, "ffh_private_data": 0,
        "only_synthetic_data": True,
    }
    (out / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('R100_SUMMARY', json.dumps(result, sort_keys=True))
    assert len(rows) == 50
    assert any(row['status'] == 'provisional_candidate' for row in rows), 'No provisional results'

if __name__ == '__main__':
    main()
