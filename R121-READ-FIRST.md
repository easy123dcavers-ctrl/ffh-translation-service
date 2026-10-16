# FFH R121 — MAIN COORDINATOR READ FIRST — 2026-10-16
Scope: **FFH TRANSLATION SERVICE only**, NOT full FFH site.
Branch: `ffh-r121d-german-recycle-20261016`.
**PRODUCTION RELEASE STATUS: HOLD. No Render, Netlify or Supabase modifications.**

## What was actually achieved
1. `ffh-r121-legacy-quarantine-security-audit-20261016` added an opt-in (OFF by default) *staging-only* legacy-route quarantine `FFH_LEGACY_QUARANTINE_STAGING_ONLY=true`, effective only alongside `FFH_GUARDED_API_STAGING_ONLY=true`. It returns HTTP **410** on legacy `POST /translate` and `POST /translate-batch`, while leaving `/health`, `/languages` and authenticated guarded endpoints available.
2. Isolated GitHub run https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38855775669: **98/98 PASS** (12 new legacy-bypass tests + the previous 86 R120 security, admission, integrity and HTTP tests). No real model in this run.
3. Reviewed pinned Argos v1.11.0 source: MIT license applies to **source code**. The Argos index model records contain links and version but do not attest model-archive SHA/license. `install_models.py` still downloads from a mutable index and only verifies observed model tree after installation. Model provenance/security/licensing remains a major blocker. See `R121-SECURITY-RISK-REGISTER.md`.
4. Designed `R121-BROKER-CONTRACT-DESIGN-ONLY.md` with FFH browser → authenticated trusted backend broker → guarded model service, and reviewed/held translation governance. This is architecture guidance **only**, not implemented Member auth or released code.

## Real 512MiB German staging tests: all outcomes, INCLUDING FAILED JOBS
All tests: disposable Docker, one German Argos model, actual Flask/Gunicorn, loopback, disabled runtime internet, 1 CPU, max 512MiB RAM and swap, random synthetic staging bearer, no real content or DB writes.

| Test | GitHub CI | Measured | Final outcome |
|---|---|---|---|
| R121 batch8, cold first 25-item guarded call | [38855947860](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38855947860) | **512.0 MiB; OOM kill=1** | **FAIL/HOLD**; legacy 410 and 401 auth had already passed, but translation crashed |
| R121b batch8, model warm-up first | [38856159941](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38856159941) | **512.0 MiB; OOM kill=1** | **FAIL/HOLD**; even warm-up did not protect memory |
| R121b batch1, cold first guarded 25-item call | same 38856159941 | **277.26 MiB; 45.85% headroom**, no OOM; legacy bypass rejected 4/4, unauthorized 401, health concurrent OK, 25 items | **PASS narrow cold-load/HTTP gate only** |
| R121c batch1, max-requests=12, 2-min intended | [38856369239](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38856369239) | **279.76 MiB; 45.36% headroom**, 50 items | **FAIL/HOLD**: client connection reset by peer while worker recycling |
| R121d batch1, max-requests=24, 2-min intended | [38856582500](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38856582500) | **280.76 MiB; 45.16% headroom**, 150 items | **FAIL/HOLD**: connection reset during worker recycling |
| R121d batch1, max-requests=48, 2-min | same 38856582500 | **282.99 MiB; 44.73% headroom**, 450 items, 18/18 HTTP 429 rejection, health responsive | **HOLD**: 2-minute application/health/size checks passed but zero intra-master worker recycling events occurred; final CI marked FAILED because recycling proof gate was unsatisfied |

Do **not** rebrand R121d 48 as a recycling success merely because its HTTP/memory subchecks passed. R120's Korean success does not automatically generalize to German. Do NOT reduce required 15% headroom or conceal lost HTTP connections.

## Why this matters
- Warm-load R118 Germany and R120 Korea success do **not** guarantee safe cold start or seamless worker replacement for German.
- The cleanest memory-safe German profile *so far* is `ARGOS_BATCH_SIZE=1`, `ARGOS_BEAM_SIZE=4`. This is **not yet** a deployable 512MiB sustained service.
- `max-requests` recycling causes intermittent connection resets under German. A new worker-count/replacement policy needs explicit request-drain handling, idempotency and failure semantics; do not blindly auto-retry unknown commit state or private text.
- Legacy production endpoints are **not** protected by the staging flags unless deliberately enabled, and the guards are not a substitute for real member-scoped server-side Auth.

## Exact branches and source files
- R121 security/quarantine: `ffh-r121-legacy-quarantine-security-audit-20261016` (`app.py`, `tests/test_r121_legacy_quarantine.py`, `.github/workflows/ffh-r121-legacy-quarantine.yml`, `R121-SECURITY-RISK-REGISTER.md`).
- R121b cold/warm: `ffh-r121b-coldstart-memory-20261016` (`tests/r121_real_migration_probe.py`, `tests/r121.Dockerfile`, `.github/workflows/ffh-r121b-cold-memory.yml`).
- R121c soak: `ffh-r121c-german-extended-safe-20261016` (`tests/r121c_extended_migration_soak.py`, `tests/r121c.Dockerfile`, `.github/workflows/ffh-r121c-german-extended.yml`).
- R121d recycle: `ffh-r121d-german-recycle-20261016` (two profile workflow `.github/workflows/ffh-r121d-german-recycle.yml`, read-only broker design and audit carried forward).
- Previous verified R120 Korean single-container cross-worker lock: see `R120-READ-FIRST.md` in predecessor branch and previous MC handoff.

## Next task with concrete acceptance gates
**R122** should independently investigate Gunicorn gthread worker lifecycle and TCP connection-reset behavior in the presence of `max_requests`. Use *diagnostic logging of connection/request state only*, never member text/secrets. Establish controlled fault-injection tests: a permitted request gets a complete response OR an explicit, safe, client-visible failure; no silent partial-success or unsafe automatic duplicate retry. Preserve CPU+512MiB bounds, staging auth, legacy 410, zero OOM, 15% memory headroom and health responsiveness. Do not simply remove worker recycling: batch1 German memory stability over many hours is unproven.

Parallel required work: security/privacy expert review of bearer authentication, model archive hashes and licenses **before download/install**, a trusted FFH member authorization broker, all nine language quality and fermentation safety governance review, and owner-controlled rollback strategy.

## Handoff ZIP evidence
Full raw GitHub Actions summary.json and Gunicorn logs, including failures, are preserved in the attached R121 MC ZIP as independent machine-checkable evidence. A GitHub PASS in a mocked QA suite is not human safety/security certification.

**HARD RULE: no merge to auto-deployed `main`; no production Render/Netlify/Supabase mutations; no Member or protected safety-source automatic approval.**
