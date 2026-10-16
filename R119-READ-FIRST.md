# FFH R119 — Authentication, privacy, client retries and model repeatability

## VERIFIED UPDATE: real-model authentication soak (2026-10-16)
https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38853882116

Both models PASSED the post-installation R113 known-tree hash equality check and ran with a randomly generated per-run staging bearer, no runtime network, no private/member text, one Gunicorn worker, two threads, one CPU, one installed model, and a hard 512 MiB cgroup.

- **German PASS:** 475 synthetic batch outputs in 19 accepted 25-item batches, 19/19 overlapping requests rejected by HTTP 429, 19 unauthorized HTTP 401 checks from two Gunicorn starts, 281.48 MiB peak, 45.02% memory headroom, max health latency 0.0815s, zero OOM kills and zero approvals/writes.
- **Korean HOLD / CI JOB FAILED:** 800 synthetic batch outputs in 32 accepted 25-item batches, 32/32 overlapping HTTP 429, HTTP 401 checks succeeded, 494.03 MiB peak with only 3.51% headroom, zero OOM kills. This VIOLATED strict >=15% reserve. More work was processed within the fixed two-minute window than in R118 (375 items), exposing a memory-growth or cumulative load issue. Do **not** interpret the successful HTTP operations as memory acceptance; the CI verdict is failure.
- Failure remediation experiment on separate branch `ffh-r119b-ko-recycle-20261016`: bounded Gunicorn worker lifetimes 12/24 requests, with the same memory, health and authentication gates. No results should be asserted without reading that run's final logs.

**Important:** These are short isolated tests, not enterprise security certification or real user authorization. Production legacy APIs remain unguarded by this new staging-only token check; release HOLD continues.

Date: 2026-10-16. **READ FIRST — SOURCE AND TEST BRANCH ONLY**
Branch: `ffh-r119-auth-privacy-client-20261016`
**PRODUCTION UNCHANGED — NO DEPLOYMENT AUTHORIZATION.**

## Verified offline CI
https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38853793905

PASS — **81/81 regression tests** with no Argos model, no user data, no external app connections:
- 14 R119 auth/cache/privacy contract tests.
- 16 bounded 429-only retry reference-policy tests.
- 8 model byte/tree integrity fail-closed tests.
- 11 R118 original admission tests.
- 18 R116 guarded candidate API tests.
- 14 R108 legacy Flask compatibility tests.
Syntax compilation passed.

## Changes and why they matter
- `app.py`: Experimental guarded HTTP endpoints now require both the disabled-by-default switch `FFH_GUARDED_API_STAGING_ONLY=true` and a bearer token configured from `FFH_GUARDED_STAGING_TOKEN` (at least 32 characters). Missing or short configuration -> 404; bad/missing Authorization header -> HTTP 401; comparison uses `hmac.compare_digest` (constant time).
- Every guarded HTTP response, including errors, 401 and 429, has `Cache-Control: no-store, private, max-age=0`, `Pragma: no-cache`, and `X-Content-Type-Options: nosniff`.
- Existing R118 1-request process-local semaphore, fail-fast 429 with Retry-After:2, 128KiB HTTP body limit, 25-item batch limit, and source integrity holds remain intact.
- `tools/r119_client_retry_contract.py`: *REFERENCE ONLY*. Deterministic bounded 429-only retry guidance: at most 3 total attempts, at most 4 seconds one delay, at most 6 seconds cumulative sleep, no retry on unauthorized (401), invalid request (400), held drafts, other errors, or malformed/too-long Retry-After. This is **not wired to FFH's browser client**.
- `tools/r119_verify_model_tree.py` and `models/r119_observed_model_trees.json`: compare file/tree digests and total byte length to exact prior R113 eight-language test-archive baselines. Unexpected version or any byte change -> STOP. This is an **after-install repeatability check**, *not* independently authenticated download archive publisher identity or supply-chain certification.
- `tests/test_r119_auth_privacy.py`, `tests/test_r119_retry_contract.py`, `tests/test_r119_model_tree.py` plus adapted `tests/test_r116_guarded_api.py` (synthetic test credentials only).

## Security limitations that still BLOCK release
1. Legacy `/translate` and `/translate-batch` remain available without staging bearer credentials and DO NOT enforce guarded source protections/admission. Real FFH client migration, backward compatibility and a rollback plan are required before exposing authenticated translation publicly. **Never claim R119 secures the legacy production API.**
2. The staging secret is a *shared test token*, NOT real FFH Member authentication/authorization, user-specific quotas, abuse rate limits, or trustworthy identity. Its presence must never imply public production readiness.
3. Real Render/private text logging, proxy, TLS, request logs, WAF/rate limits, multi-worker/admission correctness, CSRF/CORS browser integration, secret rotation, replay resistance, body size and cache interactions need independent review.
4. R102 shared cross-request cache still OFF by default; never enable for private texts without separate review.
5. Model tree hashes are derived from earlier GitHub Actions tests, not a cryptographic publisher attestation. Independently pin downloaded model archives/check publisher identities, licenses and dependency versions.
6. Review/source fidelity of translations is absent: native-speaking fermentation/science review for nine languages, safety-protected source holds and canonical English contract required.
7. Tests are invented data only. No Supabase, Netlify, Render deployments, no private content, no automatic review approvals.

## Real-model R119 status
The real German/Korean, 512MiB, disabled-runtime-network, randomized staging-token validation is a separate GitHub Actions job:
https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38853882116
**Do not claim PASS until both jobs and their summary artifacts are independently inspected.**
The job also rechecks model tree hashes during image build before runtime.

## Deployment / next steps
Production Render still auto-deploys from `main`; keep all R119 commits isolated.
After real-model verification, tackle real-client secret/account security contract, request-rate limiting, proxy log privacy, archive publisher signatures and independent multilingual safety review. Finish independent rollout QA before owner-directed release.
