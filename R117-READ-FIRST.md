# FFH R117 — SAFE LOAD-BOUNDARY RESULTS — READ FIRST
Date: 2026-10-16. **EXPERIMENTS ONLY. Production untouched. No release approved.**

## Exact verified GitHub runs
- Primary account 5-language matrix (es, fr, de, ja, ar): https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38846026764 — 5/5 PASS.
- Secondary account 4-language matrix (tl, ko, vi, zh): https://github.com/KatsuraFukuryu/ffh-translation-tests/actions/runs/38846030532 — 3 PASS, Korean initial profile FAIL MEMORY.
- Secondary Korean profile follow-up: https://github.com/KatsuraFukuryu/ffh-translation-tests/actions/runs/38846275370 — **batch1/beam4 PASS**, batch4/beam2 FAIL MEMORY.
- Experimental branches `ffh-r117-stress-matrix-a-20261016`, `ffh-r117-stress-matrix-b-20261016`, `ffh-r117b-korean-low-memory-20261016`. Nothing merged to `main`.

## Precisely what was tested (each selected passing profile)
- Real pinned lightweight Argos 1.11.0+ffhlite1, exactly one model per container, Flask/Gunicorn 1 worker/2 threads, 1 CPU, Docker memory cap=512 MiB, swap cap=512 MiB, runtime network disabled and no FFH production calls.
- Two separately started Gunicorn processes per language; each startup received a 25-entry guarded candidate batch, then **two concurrent 6-entry guarded batches** with separate HTTP health checks, plus one ~2,522-character multi-paragraph request. In total per model: **74 batch item occurrences, two long requests**; for the nine selected configurations: **666 batch items and 18 long requests**.
- Every held response had NO draft and all provisional drafts remained `human_approved=false` with zero writes. Protected `{{BATCH_ID}}` and `{{ROW_ID}}` tokens remained exact when output was provisional. Malformed tokens, URLs and over-4096-character inputs were held.
- Health HTTP 200 while full batch active and during the simultaneous two small batches. No OOM kills, no Netlify deploys, no Supabase read/write, cache OFF.

## Nine target configuration matrix — selected resource-viable profiles
| FFH locale | Argos target | Argos batch | Argos beam | Cgroup peak MiB | Headroom | R117 final |
|---|---|---:|---:|---:|---:|---|
| es | es | 8 | 4 | 222.75 | 56.49% | PASS |
| fr | fr | 8 | 4 | 215.41 | 57.93% | PASS |
| de | de | 8 | 4 | 284.96 | 44.34% | PASS |
| ja | ja | 8 | 4 | 263.75 | 48.49% | PASS |
| ar | ar | 8 | 4 | 221.08 | 56.82% | PASS |
| fil | tl | 1 | 4 | 212.48 | 58.50% | PASS |
| ko | ko | **1** | 4 | 263.83 | 48.47% | PASS |
| vi | vi | 8 | 4 | 213.38 | 58.33% | PASS |
| zh-Hans | zh | 8 | 4 | 218.28 | 57.37% | PASS for generic zh only |

## Korean rejected configurations: DO NOT ship
- Korean Argos batch 8, beam 4: cgroup peak **492.61 MiB**, headroom **3.79%**; CI FAIL/HOLD for less than 15% headroom. No OOM kill, but too unsafe.
- Korean Argos batch 4, beam 2: cgroup peak **494.21 MiB**, headroom **3.48%**; CI FAIL/HOLD for less than 15% headroom.
- Korean batch 1, beam 4: 263.83 MiB (48.47% headroom), CI PASS for resource/API only. Fewer translation threads/parallelism may reduce throughput; measure separately.
- Tagalog likewise requires batch1/beam4 based on R115/R117 memory tests.

## Responsiveness warning
These are very short tests (R117 per-model duration ~25–53 seconds). Highest single health latency while two guarded batches were active was ~**4.321 seconds for German** (test gates require less than five seconds), ~3.707 for Tagalog, ~3.175 for Chinese. Under real traffic, a two-thread translation worker can starve the health endpoint. A passing 5-second bound in two tests is NOT a statistically sound p95/p99 service-level guarantee. Rate limits, queueing and a separate health-readiness strategy require design review. No 8h soak performed.

## Translation governance
- All outputs are **unapproved, provisional**. A resource PASS does not mean a fluent translation or food-safety PASS.
- Changed numbers, units, URLs/emails, malformed placeholders and long source content trigger holds; no held draft is returned. Number/unit checks are conservative and may hold valid linguistic formatting changes.
- Risks NOT covered: locale-specific quality (`fil→tl`, `zh-Hans→zh`), Arabic RTL presentation, food-safety precision, private member content, network-facing authentication/abuse prevention, upload/retention, full scientific units and 12+ hour endurance.
- R116 guarded endpoints are DISABLED by default and not deployed. The original `/translate` and `/translate-batch` routes remain unguarded; do not misrepresent R117 as fixing those production paths.
- The modified Argos build lacks independent formal security/license/supply-chain review and model package SHA pinning prior to installation. No Netlify deployment, Render change, Supabase translation ingestion, or automated approval was performed.
- Do not deploy/merge test branches; Render auto-deploys `main`.

## Next owner-controlled engineering gate
1. R118: add safe bounded request queue/admission (one in-flight Argos translation batch per 512MiB instance), rate/request-size/timeout limits, and monitor health/p95 with sustained tests. Do not add workers to the single 512MiB instance without evidence.
2. R119: model provenance/pinning, supply-chain and security review, independent fluent linguistic + fermentation safety QA in all nine languages.
3. Only after passing real-like staging, privacy, and independent review: explicit owner-controlled rollout with rollback, no accidental merge to `main`.

R117 is a solid **RESOURCE CONCURRENCY INVESTIGATION**, not production-ready certification.
