# FFH R107 — Guarded API and local-service QA handoff

## VERIFIED UPDATE — 19 OFFLINE TESTS PASSED (2026-10-16)

- R107 isolated CI run: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38835225954
- Result: **PASS — 19 tests**, explicitly confirmed in GitHub logs (`Ran 19 tests`, `OK`). Syntax compilation of app.py, translation_cache.py, and all changed test files also passed.
- Breakdown: 8 JSON parser/route-guard contract tests plus 11 executable route-logic tests using mocked Flask/request/translation functions. These tests run real extracted app.py route function code, without importing Flask or Argos and without contacting production.
- Earlier 8-test run: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38835131045 (PASS).
- Source additions: `tests/test_r107_route_logic.py` and `.github/workflows/ffh-r107-stdlib-contract.yml`.
- **Not tested:** actual Flask request integration, the Gunicorn process, a 512 MiB environment, the low-memory unsupported Argos modification, actual translation quality, or concurrent health checks. Thus **NOT RELEASE READY**.
- The prior notes below predate this run: any prior claim that the eight offline tests were `not executed` is superseded by the verified 19-test result above. **The R106 localhost integration test remains unexecuted.**

Date: 2026-10-16

## STATUS — NO PRODUCTION CHANGES
- GitHub branch: `ffh-r107-api-input-hardening-20261016`; Render remains auto-deployed from `main` only.
- No Netlify deploy, no Supabase writes, no translation approvals, no production Render config edits.
- R107 changes are **source-prepared / read-back inspected**, **NOT integration-tested**, and **NOT release approved**.
- The R106 workflow creation previously failed an automated safety check. Do not bypass that restriction; the localhost test file exists but **no R106 or R107 HTTP/Gunicorn runner result** is claimed.

## Grounded findings
1. Earlier Render `server_failed` events on 2026-10-13 explicitly reported memory-limit (512 MiB) kills and health-check timeouts. The live Render instance had one Gunicorn worker and one thread at the time of inspection.
2. R105 synthetic script experiment produced 244.21 MiB peak memory only after a DISPOSABLE patched Argos import plus removal of Stanza/PyTorch on a GitHub runner. This is not a supported production package. No long-text, multi-language, Gunicorn or true Render-cap memory certification exists.
3. README.md documents `q`, `source`, and `target` as request fields. Missing `target` currently returns 400 by contract; **do not call that a production defect** without a caller-contract audit. Read-only Render query for 400 request logs in the requested recent range returned no matching entries, so historic 400 root cause remains UNCONFIRMED.
4. Non-object JSON root types (such as `[]` and `"text"`) previously reached `payload.get(...)` and could produce an unhandled exception. This is the narrow R107 API hardening target.

## Implemented on test branch only
- `app.py`: new `validated_json_body()` checks the parsed JSON root is an object. Both `/translate` and `/translate-batch` return controlled HTTP 400 for invalid JSON-root types. Translation engine, targets, RLS, cache default OFF, and MAX_BATCH_ITEMS=25 unchanged.
- `tests/test_r107_request_contract.py`: 8 Python-stdlib-only offline regression tests (prepared, **not executed** in GitHub). Covers object, empty object, list, string, number, null, boolean and structural guards in both routes.
- `tests/r106_localhost_service.py`: startup timeout now has a real 30-second deadline; one/two thread comparison is parameterized by `FFH_TEST_GUNICORN_THREADS`; invalid JSON array and missing-target contract checks added; health-check timeouts during batch are recorded rather than blindly treated as service errors. Measured process peak RSS is only a conservative estimate; shared RSS may be double counted.

## Static read-back verification
The GitHub connector confirmed 1 parser helper, 2 endpoint guards, the unmodified 25-item batch limit, cache still disabled by default, all 8 declared offline test methods, updated probe logic, and all files present. These are source inspections, **not test execution**.

## Required work before owner is asked to deploy
- Run the stdlib offline tests with: `python -m unittest discover -s tests -p test_r107_request_contract.py -v` on a trusted local or permitted CI environment.
- In isolated staging, test Flask/Gunicorn in a true 512 MiB memory cap with low-memory supported packaging, one vs two threads, 25-item batches and health checks under load. At least 20% memory headroom is desirable; do not infer it from the 244 MiB bare-process measurement.
- Integrate Argos through a maintained version-pinned package/source build. The R105 disposable site-packages patch is not a release procedure.
- Compare any modified engine against existing translations in each supported language; source English is canonical. Review all fermentation safety meaning, placeholders, numbers, units, and privacy.
- Investigate client payloads and status codes without leaking user-provided source text or logging secrets.
- Independently review cache behavior and member text privacy; R102 in-process cache stays OFF.
- Do not merge a test branch to `main`; it would auto-deploy Render.
- The final approval remains with the FFH owner and coordinator.

## Relevant evidence
- R105 memory B successful: https://github.com/KatsuraFukuryu/ffh-translation-tests/actions/runs/38831602671
- R105 memory A control: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38831598452
- R102 offline cache tests (9/9): https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38830318784
