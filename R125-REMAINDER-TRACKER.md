# FFH R125 — Remaining work after nine models passed short 20% memory tests
Date 2026-10-16. Translation service engineering only; main website and Supabase not changed.

## Scope and honest percentages
- **9/9 (100%)** target-language configurations have two short **isolated single-model** tests passing the exact 20%-RAM-headroom gate inside a 512MiB Docker cgroup. That does not imply 100% deployment readiness or content translated.
- R125 is the NEXT SEPARATE milestone: a **single 512MiB process may switch sequentially between models on disk, but all models cannot simply be loaded into RAM simultaneously**. R125 starts by verifying just TWO targets (Spanish, French) in ONE offline Docker image and never claims proof for all nine.
- A full-nine rotating model/one-image design might be constrained by image size, disk, switching latency, cold starts, CPU quotas, cache/privacy, and popular-language demand; all require measurement, not inference. No statement of total project-completion percentage is yet warranted.

## Isolated implementation under test
- Branch: `ffh-r125-single-instance-model-switch-20261016` (derived from previously guarded test branch `ffh-r124c-vietnamese-headroom20-20261016`).
- `tests/r125.Dockerfile` installs two previously seen model trees EN→ES and EN→FR into **different read-only model directories** and verifies each against stored post-install hashes. It presents exactly one model directory to Flask by a test-only atomic symlink selected during a no-client, no-worker interval. Actual packages on disk do NOT imply both models loaded into RAM.
- `tests/r125_serial_gateway.py` is loopback-only, test-only: one active language at a time; an authenticated request for the wrong loaded language returns `503` with Retry-After; old unguarded endpoints return 410, and 401 for missing shared synthetic staging bearer. This is **not** member authorization.
- `tests/r125_serial_switch.py` uses one backend process at a time and planned idle drain+switch, tested through ES→FR→ES→FR with real invented book data, 25-item batches, 429 during ongoing requests, 503 during switch gaps, and fresh Gunicorn worker after every model switch. It must retain at least 20% of 512MiB (max peak 409.6MiB), zero OOM. Test only, NO production integration.
- `tests/test_r125_router_contract.py` tests the wrong-language, draining, authorization and release invariant without model downloads.
- Workflow: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/workflows/ffh-r125-serial-switch.yml

## Seven remaining real-release workstreams
1. Safe **nine-language serving on a single free instance**: quantify image/disk cost of 9 models, safe serialized model loading/unloading, switching latency, language popularity, language dispatch, queueing, starvation, uptime, and cold start. Stage without exposing a public test gateway.
2. **Long-run reliability and crash handling**: each model 30+ minute load; memory leakage after repeated switching, 512MiB+20% reserve on every startup and switch, unexpected SIGKILL/termination and incomplete outputs, no duplicate automatic replay.
3. **Real FFH member authentication/broker**: owner/admin/member roles and JWT/session verified server-side, secret rotation, rate limits, quotas. Never put a single shared stage bearer in public Netlify JS.
4. **Legacy route/client migration**: old public `/translate`, `/translate-batch` do NOT have stage-only protected controls in production; require supported client-migration plan, backwards-compatibility, secure retirement, bounded mobile retry and graceful degraded English fallback.
5. **Independent model provenance, privacy and security**: model download archive publisher identity + checksum BEFORE install, license, dependency audit, private-text logging and retention, modified Argos security review.
6. **Content correctness/science**: human, independent fluent review for each of nine language target mappings, fermentation safety numbers/salinity/acidity/temperatures, accurate `fil→tl`, `zh-Hans→zh`, RTL Arabic. A resource test is NOT a translation approval. Safe Reviewer approvals must not be bypassed.
7. **Owner-controlled stage, rollout and rollback**: true Render/Netlify/Supabase dummy-member end-to-end tests, clear acceptance/monitoring and precise rollback; group Netlify updates to minimize paid deployment credits.

## Immutable boundary
Render deploys production from `main`; NEVER merge/commit to `main` as an experiment. Never deploy Netlify, mutate Supabase, publish machine translations, alter food-safety classifications, or disable existing approval gates. The R125 gateway is internal test code and MUST NOT be treated as a trusted user-facing broker.

**Production release HOLD.**
