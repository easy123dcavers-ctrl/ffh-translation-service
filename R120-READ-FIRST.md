# FFH R120 — READ FIRST — single-container cross-worker admission recovery
Date: 2026-10-16.
**STATUS: RESOURCE/SECURITY ENGINEERING TEST PASSED; PRODUCTION RELEASE REMAINS HOLD.**
Branch `ffh-r120-cross-worker-admission-20261016`. Never merge to Render auto-deployed `main` without owner-directed release acceptance and rollback.

## Verified tool-run evidence
- R119 authenticated/offline security contracts: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38853793905 — **81/81** PASS.
- R119 real-model 512 MiB soak: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38853882116 — German PASS (475 items, 281.48 MiB peak, 45.02% headroom), Korean **FAIL** at 494.03 MiB peak, only 3.51% margin although 800 items translated and no OOM kill.
- R119b worker recycling without shared lock: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38854302391 — **BOTH Korean profiles FAILED**: at 24 max-requests, 253.78 MiB peak but overlapping request was not reliably rejected with HTTP 429; at 12 max-requests, 259.74 MiB peak but same concurrency failure. A BoundedSemaphore is *process local* and does not cover overlapping old/new Gunicorn worker processes during recycling.
- R120 isolated cross-process lock suite: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38854709482 — **86/86** tests PASS (5 new Linux cross-process/symlink/lock-release tests plus 81 R119/older tests).
- R120 actual Korean 512 MiB hard-cgroup, offline Gunicorn stress: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38854734142 — **BOTH profiles PASS**. Each included authenticated staging traffic, real 25-item batches, deliberately overlapping requests, two Gunicorn master restarts, several workers recycled automatically, and verified model tree hash. Model `en→ko`, Argos 1.11.0+ffhlite1 with Argos batch 1, beam 4.

| R120 measure | max-requests=12 | max-requests=24 |
|---|---:|---:|
| Total soak seconds | 122.79 | 127.08 |
| Guarded 25-item batches accepted | 38 | 15 |
| Batch items | 950 | 375 |
| Deliberate competing requests rejected 429 | 38/38 | 15/15 |
| Peak actual container cgroup memory | 259.80 MiB | 258.51 MiB |
| Remaining memory headroom | 49.26% | 49.51% |
| Slowest observed health HTTP | 0.0185 sec | 0.0793 sec |
| HTTP 429 maximum response latency | 0.5524 sec | 0.7314 sec |
| Gunicorn workers booted over 2 master runs | 11 | 4 |
| OOM kills | 0 | 0 |
| Held entries (draft withheld) | 76 | 30 |
| Provisional candidates only | 874 | 345 |
| Human approvals, production writes | 0, 0 | 0, 0 |

**The jobs and strict final memory assertions PASSED.** The JSON summary's legacy intermediate string `PASS_ADMISSION_AND_RESOURCE_PENDING_FINAL_CGROUP` is not a release verdict; the authoritative CI job completed all gates successfully. This report supersedes the outdated assertion that Korean is safe under any worker-recycle setting.

## Code, tests and runtime boundaries
- `app.py`: experimental guarded APIs require opt-in stage flag **and** a secret staging bearer (>=32 characters) validated using `hmac.compare_digest`; return 404 when disabled or misconfigured; 401 for invalid bearer; `Cache-Control: no-store, private`, `Pragma: no-cache`.
- R118 local `BoundedSemaphore(1)` is retained. R120 adds fail-fast **Linux `fcntl.flock`** on a constant local file path shared by overlapping Gunicorn workers in ONE container. Nonblocking lock failures return sanitized 429 and Retry-After:2; lock-opening failures return sanitized 503, never run the model. Symlinks refused; file-owner verified; all locks released in `finally`.
- CI uses 1 CPU, hard 512MiB Docker cgroup, swap=512MiB, no runtime network, *one installed model*, 1 Gunicorn master with 1 worker/2 threads, and build-time preinstalled MiniSBD assets. The bearer token is randomly generated for each job and passed at runtime; no production secrets exist in GitHub.
- `tools/r119_verify_model_tree.py` compares installed model tree to earlier observed R113 file contents. The Korean tree checksum equals `b2b262876d3c840198bafdabd22ba0a683c359104ce16e527debe478f329473d`. It **does not** authenticate upstream publisher or archive signatures.
- R120 experiments use `tests/r119_authenticated_soak.py` modified to configure and prove Gunicorn `max-requests` recycling, `tests/r119.Dockerfile`, `.github/workflows/ffh-r120-offline-contract.yml`, `.github/workflows/ffh-r120-real-recycle.yml` and `tests/test_r120_cross_worker.py`.
- Reference-only client bounded 429 retry contract: `tools/r119_client_retry_contract.py`. It is **not** integrated into Netlify's browser client.

## Critical production BLOCKERS — do not bypass
1. The old live `/translate` and `/translate-batch` remain unchanged, unauthenticated by the new guarded staging token, and outside the guarded integrity/admission queue. R120's protection **DOES NOT** secure these legacy endpoints. A deliberately designed and QA'd client-migration and legacy route retirement plan is mandatory.
2. The staging bearer token is **NOT Member/Owner authentication**. Never put a shared secret in public Netlify JavaScript. A trusted backend, session/claim validation, per-user quotas and abuse protection are not implemented.
3. The file lock spans threads and recycling workers only in **one local Linux container**, NOT multiple Render service replicas or machines. No distributed admission/queue or scaling support is proven.
4. These are two-minute, synthetic, one-model trials; the big difference between 950 and 375 items is not a controlled throughput guarantee. Real production mixes, slow clients, retries, cancellation, network disruptions, many hours of service life and long-text memory tails remain untested.
5. Model tree repeatability is not model archive pin-before-install, cryptographic publisher trust, independent supply-chain/security/license review.
6. All nine language models have isolated resource profiles, but **not** authenticated admission/recycle tests across all nine. The FFH `fil→tl`, `zh-Hans→zh`, Arabic RTL and all fermentation science/safety translations demand independent native-speaker reviews. Zero safety/protected content approvals.
7. R102 shared translation cache remains disabled; private/source member text requires a separate approved confidentiality design; log retention, service TLS and auth failure policies need professional review.
8. Owner approval, staged Render production-equivalent deployment, monitoring/rollback and Netlify/Supabase integration tests remain outstanding. Do not merge experimental branches into `main` as a test.

## Suggested next ticket
R121: **perform independent privacy/security and supply-chain review, design production Member-scoped token broker without browser-exposed shared secrets, and migrate legacy endpoints behind audited controls**. Also run longer multi-language soak and real-like traffic tests before any deployment.

**PRODUCTION remains unchanged. Render/Netlify/Supabase: zero writes; no translation approvals.**
