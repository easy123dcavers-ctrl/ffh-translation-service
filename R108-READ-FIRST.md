# FFH R108 — Flask HTTP QA — READ FIRST
Date: 2026-10-16
Scope: isolated, synthetic-only, read-only to production.

## Verified acceptance evidence
- **R107:** 19/19 Python standard-library API contract tests passed with compiled modules.
  https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38835225954
- **R108:** 14/14 Flask HTTP request/response tests passed with compiled modules.
  https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38835482645
- **33 passing tests across the two isolated runs**, rather than 33 distinct test cases in a single run.
- Branch: `ffh-r108-flask-mocked-http-20261016`; nothing was merged to `main`.
- Tests use **invented English source strings**, a fake Argos module, and Flask's test client.
- R108 installs Flask only, not Argos or translation models. No Render or Supabase network calls, no Netlify uploads.

## Test cases
Real Flask test-client routing verifies: GET /health, GET /, GET /languages; POST /translate; POST /translate-batch with string/object inputs and IDs; invalid JSON roots; malformed and non-JSON bodies; source/target errors; missing target remains HTTP 400 under the documented contract; 25 accepted and 26 rejected; per-item errors and sanitized engine exceptions.

## What passed does NOT prove
- Neither benchmark exercises the real Argos translation model inside Flask or Gunicorn.
- The 512 MiB memory bound has not been validated for Flask + Gunicorn + lightweight Argos.
- R105's 244 MiB peak was from one isolated translator process, with an unsupported test-runner Argos source edit and removed optional dependencies.
- Stanza/PyTorch removal without an adapted upstream import failed; do not copy the temporary runner patch into Render.
- Neither run checked accuracy of generated Spanish or any other language.
- The R102 cache remains disabled by default; member-private strings must not enter an unreviewed shared cache.
- The 2026-10-13 Render 512Mi OOM and health-check timeout evidence remains a genuine production reliability blocker.
- The R106 real low-memory Gunicorn workflow was not executed because the workflow setup was blocked. No workaround is authorized here.

## Next responsible milestone
1. Obtain a supported, repeatable memory-light translation package/build (licensing/upstream review, pinned dependencies, integrity validation) without ad-hoc installed-package mutation.
2. Test **real Argos** and Gunicorn under a true 512 MiB limit with headroom, 25-item batch, one and two threads, concurrent /health and restart behavior. Use only isolated data and environments; do not use production.
3. Independently review multilingual behavior, placeholders, numbers, units, fermentation safety language, and source-translation quality.
4. Inspect the caller contracts before changing required target or raising batch caps.
5. Owner-controlled approval and rollback plan before merging to `main`, because the Render service auto-deploys it.

## Current release decision
**HOLD / NOT PRODUCTION READY.** This run improves API confidence, not model memory safety.
