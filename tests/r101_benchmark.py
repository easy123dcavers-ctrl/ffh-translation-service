"""FFH R101: isolated synthetic benchmark. No FFH records, credentials, or writes."""
import argparse
import hashlib
import json
import re
import resource
import time
from collections import Counter
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
    "Label jar {n} with the date.",
    "A notebook contains {n} pages of harmless examples.",
)
NUMBERS = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?")
MARKERS = re.compile(r"\{\{[A-Z][A-Z0-9_]*\}\}")

def samples():
    return [{"id": ix * 20 + n - 1, "source": template.format(n=n)}
            for ix, template in enumerate(TEMPLATES) for n in range(1, 21)]

def tokens(pattern, value):
    return sorted(match.replace(",", ".") for match in pattern.findall(value))

def check(source, draft):
    flags = []
    if not isinstance(draft, str) or not draft.strip():
        return ["empty"]
    if source.strip() == draft.strip():
        flags.append("unchanged")
    if tokens(NUMBERS, source) != tokens(NUMBERS, draft):
        flags.append("number_mismatch")
    if tokens(MARKERS, source) != tokens(MARKERS, draft):
        flags.append("placeholder_mismatch")
    return flags

def self_test():
    assert not check("Use 12 g in {{TEST_ID}}.", "Use 12 g in {{TEST_ID}}!")
    assert "number_mismatch" in check("Use 12 g.", "Use 13 g.")
    assert "placeholder_mismatch" in check("ID {{TEST_ID}}.", "ID.")
    assert "empty" in check("Hello 1.", "")
    assert "unchanged" in check("Hello 1.", "Hello 1.")

def run_pass(texts, translate, cached):
    cache = {}
    results = []
    calls = 0
    hit = 0
    t0 = time.perf_counter()
    for source in texts:
        if cached and source in cache:
            draft = cache[source]
            hit += 1
        else:
            draft = translate(source)
            calls += 1
            if cached:
                cache[source] = draft
        results.append(draft)
    elapsed = time.perf_counter() - t0
    return results, round(elapsed, 4), calls, hit

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-index", type=int, required=True, choices=(0, 1))
    parser.add_argument("--target", choices=("es", "fr", "ja"), default="es")
    parser.add_argument("--output-dir", default="r101-output")
    args = parser.parse_args()
    self_test()
    full = samples()
    assert len(full) == 240
    assert len(set(x["id"] for x in full)) == 240
    assert len(set(x["source"] for x in full)) == 240
    groups = [[x for x in full if x["id"] % 2 == k] for k in (0, 1)]
    assert all(len(group) == 120 for group in groups)
    assert set(x["id"] for x in groups[0]).isdisjoint(
        set(x["id"] for x in groups[1]))
    assert {x["id"] for group in groups for x in group} == set(range(240))
    selected = groups[args.shard_index]
    unique = [x["source"] for x in selected]
    repeated = unique + unique
    assert len(repeated) == 240 and len(set(repeated)) == 120

    import argostranslate.package as pkg
    import argostranslate.translate as tx
    setup_start = time.perf_counter()
    pkg.update_package_index()
    model = next((p for p in pkg.get_available_packages()
                  if p.from_code == "en" and p.to_code == args.target), None)
    if model is None:
        raise RuntimeError("No direct Argos en-" + args.target + " package")
    version = str(model.package_version)
    pkg.install_from_path(model.download())
    model_setup_seconds = round(time.perf_counter() - setup_start, 3)
    translate = lambda s: tx.translate(s, "en", args.target)
    # Warm once, so the cached/uncached comparison does not include model startup.
    translate("This is an invented test sentence.")

    unique_drafts, unique_s, unique_calls, _ = run_pass(unique, translate, False)
    uncached_drafts, uncached_s, uncached_calls, _ = run_pass(repeated, translate, False)
    cached_drafts, cached_s, cached_calls, cache_hits = run_pass(repeated, translate, True)

    # A cache may not change draft content; order and identities must match exactly.
    assert cached_drafts == uncached_drafts
    assert unique_drafts == uncached_drafts[:120]
    assert unique_calls == 120 and uncached_calls == 240
    assert cached_calls == 120 and cache_hits == 120
    assert len(cached_drafts) == 240

    flags_by_record = [check(source, draft) for source, draft
                       in zip(repeated, cached_drafts)]
    flag_counts = Counter(flag for row in flags_by_record for flag in row)
    held = sum(bool(row) for row in flags_by_record)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "test": "R101-isolated-two-account-benchmark",
        "target": args.target, "model_version": version,
        "shard_index": args.shard_index, "shard_count": 2,
        "total_unique_source_count": len(full),
        "unique_per_worker": 120, "repeated_per_worker": 240,
        "sample_ids_sha256": hashlib.sha256(
            json.dumps([x["id"] for x in selected]).encode()).hexdigest(),
        "python_model_setup_seconds": model_setup_seconds,
        "unique_uncached_seconds": round(unique_s, 3),
        "repeated_uncached_seconds": round(uncached_s, 3),
        "repeated_cached_seconds": round(cached_s, 3),
        "cached_translation_calls": cached_calls, "cache_hits": cache_hits,
        "cache_hit_rate": 0.5,
        "repeated_cache_speedup_factor": round(uncached_s / max(cached_s, 0.00001), 2),
        "held_output_occurrences": held,
        "provisional_output_occurrences": 240 - held,
        "validation_flag_counts": dict(flag_counts),
        "peak_process_memory_mb": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "human_approved": 0, "production_writes": 0,
        "ffh_private_data": 0, "only_synthetic_data": True,
        "accuracy_reviewed": False,
        "note": "Exploratory sequential pass; cached pass occurs after uncached pass."
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (out / "synthetic_drafts.jsonl").open("w", encoding="utf-8") as handle:
        for index, (src, draft, flags) in enumerate(
                zip(repeated, cached_drafts, flags_by_record)):
            handle.write(json.dumps({
                "synthetic_id": selected[index % 120]["id"], "occurrence": index // 120,
                "source": src, "draft": draft,
                "flags": flags,
                "status": "held" if flags else "provisional_candidate"
            }, ensure_ascii=False) + "\n")
    print("R101_SUMMARY", json.dumps(summary, sort_keys=True))
    assert summary["only_synthetic_data"] and summary["production_writes"] == 0
    assert summary["human_approved"] == 0
    assert summary["provisional_output_occurrences"] > 0

if __name__ == "__main__":
    main()
