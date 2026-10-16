# FFH R101 — Verified two-worker synthetic benchmark (2026-10-16)

## Scope and safety
- Both experiments operated on separate test-only GitHub branches and invented English sentences.
- ZERO production Supabase writes, ZERO Netlify deployments, ZERO Render changes, ZERO approvals.
- Model: Argos en->es direct model version 1.0 via argostranslate 1.11.0.
- Each shard owns a disjoint partition of 120 unique IDs from a 240-item synthetic source set.
- Each shard tested 240 input occurrences: 120 distinct sources repeated once.
- Workflow output classification is PROVISIONAL; automated number/placeholder checks are not linguistic or food-safety validation.

## R100 baseline
| Measure | Worker A | Worker B |
|---|---:|---:|
| 50 distinct synthetic inputs, translating only | 7.686s | 4.689s |
| Peak process memory | 902.4 MB | 912.5 MB |
| Held | 0 | 0 |
| GitHub workflow | https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38823434907 | https://github.com/KatsuraFukuryu/ffh-translation-tests/actions/runs/38828865997 |
| Pip dependency installation stage | 77s | 104s |

## R101 repeated-input benchmark
| Measure | Worker A | Worker B |
|---|---:|---:|
| Unique inputs per shard | 120 | 120 |
| Input occurrences per repeated run | 240 | 240 |
| Repeated, no cache | 16.305s | 10.608s |
| Repeated, cached | 8.145s | 5.331s |
| Reduction in translation calls | 240 -> 120 | 240 -> 120 |
| Repeated-input speed improvement | 2.00x | 1.99x |
| Peak process memory | 915.6 MB | 916.6 MB |
| Output occurrences flagged by mechanical checks | 0 | 0 |
| GitHub full job time | 149s | 225s |
| Pip install stage | 100s | 191s |
| Model setup inside benchmark process | 3.130s | 2.269s |
| GitHub workflow | https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38829603069 | https://github.com/KatsuraFukuryu/ffh-translation-tests/actions/runs/38829606945 |

The R101 jobs ran at overlapping times (Worker A 00:27:47–00:30:16 UTC; Worker B 00:27:49–00:31:34 UTC). Parallel orchestration is technically functional. Note that GitHub runner startup and dependency setup dominate the end-to-end time and vary greatly. Performance numbers are exploratory: the cached pass ran after the uncached pass and the duplicate-heavy dataset was deliberately synthetic.

## Proposed next engineering ticket (NOT YET IMPLEMENTED)
1. Apply a bounded in-process source-string deduplication and per-language, per-model-version cache to the existing **long-lived** translator backend, on a separate reviewed change branch. Do not put this ephemeral GitHub Actions harness into production.
2. Key by exact normalized source + target language + translator model/version; never mix protected reviewed source values with provisional drafts. Set a cache size/TTL limit. Do not cache failures or transient HTTP errors. Add concurrency and invalidation tests.
3. Measure actual production-shaped translation payloads *offline*, without secrets or production DB writes: unique/repeated ratios, language coverage, memory, cache eviction, CPU, restart behavior.
4. The observed Argos process memory around 900+ MB exceeds the historical 512 MB free Render service limit. STOP before moving this test harness or increasing workers on that Render instance. Determine whether a lower-memory model/worker strategy is needed.
5. Ensure translation QA checks numerals, units, interpolation placeholders, URLs, locale punctuation and domain-specific fermentation/safety meaning. A fluent reviewer must approve content. Safety-gated sources remain held pending the existing designated approval process.
6. For public GitHub test workflows, budget total job time and dependency install; do not use GitHub Actions as an always-on production translation service or to evade compute limits.
7. Maintain the immutable FFH English source as canonical, keep nine-language support language-generic, and preserve reviewed-state immutability and all FFH safety exclusion rules.

## How to reproduce
Read tests/r101_benchmark.py and the R101 workflow file on the same branch. Compare each workflow's R101_SUMMARY log entry. The downloadable synthetic JSON artifacts are retained only for three days.
