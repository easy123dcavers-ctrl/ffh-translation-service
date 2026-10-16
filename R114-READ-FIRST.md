# FFH R114 — Experimental Protected Text Gate — READ FIRST
Date: 2026-10-16. Branch: `ffh-r114-protected-source-qa-20261016`. Production unchanged.

## Verified test runs
- Offline pure-Python guards: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38839648466 — 16/16 tests passed.
- Real Argos Arabic and Chinese: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38839787533 — BOTH model tests passed under actual 512 MiB Docker cgroup with network disabled at runtime.

## Real-model results
Both `ar` and `zh` passed 4 invented-source cases with experimental `guarded_candidate` wrapper. Each:
- Preserved one or two literal `{{TOKEN}}` placeholders without sending protected tokens to model.
- Returned 2 provisional draft candidates (NOT APPROVED).
- Held 2 source strings without exposing translation draft: one changed original measurement units, one changed numeric values.
- Retained zero production writes and zero approvals.
- Process cgroup peak for this Python-only experimental guard runner: Arabic 189.95 MiB; Chinese 186.91 MiB. **These are not new Gunicorn measurements**, because the R114 real-model test executes the Argos module directly in its Docker container.

## Code
- `protected_translation.py`: no network or persistent IO, splits exact `{{UPPERCASE_TOKEN}}` markers away from source spans before invoking caller-supplied translator, reconstructs exact protected placeholders; holds if number/measurement integrity checks fail, if source malformed, if translation fails/empty, if too long or too many placeholders.
- `tests/test_r114_protected_translation.py`: 16 offline pure-Python tests covering Unicode numerals, placeholders, unit changes, limits and exceptions.
- `tests/r114_actual_model_qa.py`, `tests/r114.Dockerfile`, `.github/workflows/ffh-r114-real-model-protected.yml`: real isolated Arabic/Chinese smoke with pinned lightweight Argos package.

## Remaining blockers
- R114 is an experimental candidate library; it is **NOT wired into app.py, FFH databases or site**.
- Splitting text around placeholders affects context and can affect linguistic quality. Independent fluent language review is mandatory, particularly safety meaning.
- Numeric and unit normalization can trigger conservative false positives, which MUST be held rather than silently approved.
- `fil/tl` memory headroom remained inadequate in R113; R115 is investigating.
- Source length/request size, malformed curly-brace patterns, URLs/emails, RTL, privacy and authenticated approval handling need additional controlled tests.
- All outputs stay provisional; never auto-approve safety-protected content or bypass reviewed-state safeguards.
- Don't merge experimental branches into `main`; Render auto-deploys from it. No production deploy authorization.
