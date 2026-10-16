# FFH R118 — Guarded admission and 512MiB health-soak — READ FIRST
Date: 2026-10-16. Test branch: `ffh-r118-admission-soak-20261016`.
**PRODUCTION: NOT DEPLOYED / DO NOT MERGE MAIN.** English-source provisional candidates only. No Supabase or Netlify actions.

## VERIFIED
Offline Flask regression: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38847159112 — 11 R118 admission tests + 18 R116 guarded API tests + 14 R108 legacy endpoint tests, **43/43 PASS**, including syntax compilation. Earlier run 38847085877 failed because absent-body JSON returned 411 rather than the existing 400. The implementation was corrected and the complete 43-test rerun PASSED.

Real German and Korean Argos + Gunicorn stress: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38847303928 — **BOTH JOBS PASSED**.

| Measurement | German (de) | Korean (ko) |
|---|---:|---:|
| Argos batch / beam | 8 / 4 | 1 / 4 |
| Soak wall time | 127.64 s | 122.17 s |
| Gunicorn startups | 2 | 2 |
| 25-item batches accepted | 18 | 15 |
| Batch items processed | 450 | 375 |
| Overlapping requests rejected HTTP 429 | 18/18 | 15/15 |
| Largest rejection response duration | 0.0836 s | 0.0497 s |
| Health p95 during batch | 0.0038 s | 0.0041 s |
| Slowest health check | 0.0818 s | 0.0792 s |
| Peak 512MiB cgroup memory | 282.68 MiB | 255.55 MiB |
| Remaining cgroup headroom | 44.79% | 50.09% |
| OOM kills | 0 | 0 |
| Held without draft | 36 | 30 |
| Provisional (unapproved) | 414 | 345 |
| Human approvals / production writes | 0 / 0 | 0 / 0 |

Combined **825 batch outputs**, **33 deliberately overlapping HTTP 429 rejections**, **66 held outputs**, **759 provisional candidates**, zero OOM kills. All data invented. No held draft ever returned; no automatic approvals.

## IMPLEMENTATION
- `app.py`: staging-only guarded API remains DISABLED by default. An in-process `BoundedSemaphore(1)` limits at most one *guarded request* per worker at once, covering an entire batch. Second guarded request gets immediate HTTP 429 JSON `{error:"translation service busy",retryable:true,retry_after_seconds:2}` with `Retry-After: 2` and does not enter a queue. Semaphore released in `finally`, including exceptions. Source/private text is not echoed in rejection.
- Body length of guarded requests bounded to 128 KiB. Missing body returns 400 (preserves legacy test semantics), bodies over cap return 413. Up to 25 items in a batch; each protected source at most 4096 characters; model integrity guard remains.
- Legacy `/translate` and `/translate-batch` remain UNCHANGED and NOT covered by this admission control.
- `tests/test_r118_admission.py`: 11 offline mocked Flask tests of admission/response/health/error cleanup.
- `tests/r118_admission_soak.py`, `tests/r118.Dockerfile`, and the two-workload matrix workflow `.github/workflows/ffh-r118-512m-soak.yml`. Hard Docker cgroup 512 MiB, 1 CPU, one Gunicorn worker/2 threads, no runtime network, pre-installed source-pinned Argos lightweight package/model and MiniSBD resources.

### VERY IMPORTANT TEST-STATUS LABEL
The current synthetic report writer stores the intermediate string `PASS_ADMISSION_AND_RESOURCE_PENDING_FINAL_CGROUP` before the final out-of-memory and minimum 15%-headroom assertions. **The GitHub CI job passed, and both final assertions completed successfully**, so the verified verdict is PASS for R118 experimental resource/admission tests. Do not interpret the intermediate label as production certification. Improve report final-state ordering in a subsequent QA ticket. It does not override the CI result.

## LIMITATIONS / NEXT RELEASE GATES
1. These are 2-minute synthetic tests, not 8–24 hour real-traffic soak, and comparisons with R117 German health latency of 4.321s are NOT a controlled same-load comparison (R118 rejects overlapping requests rather than translating both).
2. The semaphore is **process-local**, effective only with exactly one Gunicorn worker and one service replica. Multiple workers/instances require a shared admission/queue architecture. Do not casually raise workers on a 512 MiB free instance.
3. The `429` contract requires client-side retry/backoff and UX decisions; **NO public client integration done**. Protected paths remain disabled in production. No public authentication, user quotas, WAF, per-user rate limits or privacy assessment. Do not enable without these.
4. No human scientific/linguistic fermentation QA completed. Provisional outputs are not reviewed or approved. Arabic RTL, Filipino vs Tagalog, Simplified Chinese vs general Chinese and numerical/unit integrity remain pending.
5. The custom Argos source build and downloaded model files require independent supply-chain, license, checksum and update review.
6. No production Render/Netlify/Supabase mutations; no Netlify credits used. Do not merge this branch into auto-deployed Render `main`.
7. Next milestone R119: independent security/privacy review, real-client backoff/timeout contracts, model and license provenance, longer representative operational test. Then qualified linguistic and safety review and a rollback plan for owner-approved release.

## EVIDENCE ARTIFACTS
- `r118-admission-de` (GitHub artifact ID 12023633250) with `summary.json`, two Gunicorn logs.
- `r118-admission-ko` (GitHub artifact ID 12024191196) with `summary.json`, two Gunicorn logs.
- CI artifacts are short-retention; preserve them in MC handoff, with hashes.
**RELEASE VERDICT: HOLD / DO NOT DEPLOY.**
