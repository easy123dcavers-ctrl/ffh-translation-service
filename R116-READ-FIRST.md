# FFH R116 — Guarded translation API integration — READ FIRST
2026-10-16. **TEST ONLY. PRODUCTION RELEASE HOLD.**

## Verified independent CI evidence
1. Mocked Flask and existing API regression: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38845057587 **PASS** (16 original R114 protected-text tests + 18 new R116 guarded HTTP tests + 14 legacy R108 HTTP tests = **48 tests**, all passed, syntax passed).
2. Actual Argos + Gunicorn, 512 MiB capped Docker, runtime network disabled: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38845220105 **PASS BOTH Arabic and Chinese**.
3. CI evidence artifacts: `ffh-r116-guarded-ar` and `ffh-r116-guarded-zh`; retention 3 days.

| Measured | Arabic (ar) | Chinese (zh) |
|---|---:|---:|
| Cgroup memory peak | 213.01 MiB | 210.17 MiB |
| Remaining headroom | 58.40% | 58.95% |
| Active batch health | 200 in .004s | 200 in .081s |
| Provisional candidates | 5 | 5 |
| Held without draft | 5 | 5 |
| OOM kills | 0 | 0 |
| Existing /translate regression | PASS | PASS |

Each model tested 10 invented batch cases. Held reasons per model: malformed_placeholder=1; numeric_integrity=1; unit_integrity=1; unprotected_url_or_email=2. Both preserved tokens `{{SAMPLE_ID}}`, `{{ONE}}`, `{{TWO}}` where present; original text segments with placeholders were never directly passed to Argos.

## Code
- On branch `ffh-r116-guarded-api-staging-20261016` only.
- `protected_translation.py` — source integrity gate from R114.
- `app.py` — R116 experimental guarded API paths `/experimental/guarded-translate` and `/experimental/guarded-translate-batch`, accessible only when `FFH_GUARDED_API_STAGING_ONLY=true`. Disabled by default (HTTP 404 otherwise).
- `tests/test_r116_guarded_api.py` — 18 Flask integration regressions with fake Argos and no network.
- `tests/r116_real_guarded_gunicorn.py`, `tests/r116.Dockerfile`, `.github/workflows/ffh-r116-real-guarded-gunicorn.yml` — true service tests with exact pinned lightweight Argos, real Arabic and Chinese models, 512MiB cgroup, loopback-only and no runtime network.
- `.github/workflows/ffh-r116-guarded-api-qa.yml` — offline 48-test suite.

## Behavior boundaries
- **Not connected to FFH public site, Supabase, reviewed translations or safety approvals.** Human approved=FALSE always, production writes=0.
- Existing regular `/translate` and `/translate-batch` continue unchanged and are **NOT** protected by the experimental gate. This is NOT a production fix for old APIs yet.
- New guarded routes have no approved production authentication, privacy review, request-rate controls, or client rollout. **DO NOT ENABLE ON PUBLIC RENDER**. Translators could process personal/member content if enabled; staging tests contained invented strings only.
- Even provisional results may be linguistically wrong or unsafe for fermenting; none become reviewed, published, or approved automatically.
- The target API caps guarded batch count at 25; `guarded_candidate` holds input over 4096 chars or over 20 explicit placeholders. URLs/emails conservatively held before translation; no shared cache used for these guarded paths even if legacy R102 cache were enabled.
- This proof protects **exact uppercase double-brace tokens** and checks specific numeric/measurement patterns; it does not certify all possible placeholders, scientific units, context, decimal formatting, URL/email patterns or localized scripts. The R114 splitting strategy can impair sentence-context quality.
- `fil`→`tl` mapping and `zh-Hans`→`zh` script remain independent linguistic-review requirements.
- All resource tests remain per-model; 512 MiB does NOT fit nine models at once. Tagalog's low-memory config remains a separate requirement.

## Next independently reviewed gates
1. Separate *production-ready* design from test-only endpoints; owner-approved authenticated/abuse-limited API contract, privacy/data retention review, standardized user-safe error formats, explicit release toggle strategy.
2. Expand R116 real-model safeguard tests to all nine FFH target languages, including Tagalog batch1/beam4, with per-target 512 MiB measurements. Confirm protected marker semantics, numbers, units, URLs, RTL and source length bounds.
3. Independent qualified human review of fermentation safety and intended translation meaning; do not auto-approve or ingest anything in Supabase.
4. Stress real traffic-shaped workloads, retries, timeouts, malicious/malformed inputs, race testing, cold/restart behavior and one-instance memory headroom.
5. Supply-chain/language-model license audit, exact model hashes, bounded CPU/workload protections and rollback procedure. Owner approval required for controlled Render deployment.
6. Full FFH MC handoff should include the broader website and Supabase state; this report and ZIP concern the translation-service engineering only.

## Production state
**HOLD — no Render/Netlify deployment, no Supabase changes, no automatic approval.** Do not merge this branch into `main` because Render auto-deploys `main`.
