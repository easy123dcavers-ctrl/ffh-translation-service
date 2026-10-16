# R109 — Pinned lightweight Argos test build — READ FIRST
Date: 2026-10-16. Branch: ffh-r109-pinned-lightweight-build-20261016. Test-only; not production deployed.

## Verified successful GitHub CI
PASS: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38836348704

Evidence from job logs:
- 7/7 standard-library source-build tests passed.
- Downloaded the official upstream Argos Translate v1.11.0 tag, checked immutable commit `63b84ecb46c740c7a7c066d58636434d3e893ebf`.
- Attributed source-level patch transforms eager Stanza import into optional try/except, removes the `stanza==1.10.1` dependency (including PyTorch dependency in this environment), and versions test distribution `1.11.0+ffhlite1`. Retains original MIT LICENSE and upstream source checksums in generated manifest.
- `pip check` passed with the modified package requirements.
- Actual Argos English->Spanish model installed, actual Flask app exercised on GitHub runner.
- Single and 25-item batch translations, health status, invalid-input HTTP 400 passed.
- `peak_test_process_mib=250.07`, `torch_loaded=false`, `stanza_installed=false`, `cache_enabled=false`.
- All tests used invented source text. `production_writes=0`, `netlify_deploys=0`.

## Earlier failed first run
https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38836238939
First script used `python tests/r109_real_argos_flask_smoke.py` and failed importing top-level app.py due to Python import path; the script was corrected and the complete run then passed. This failure was not a translation engine bug.

## Sources and guardrails
- `tools/r109_prepare_lightweight_source.py`
- `tests/test_r109_source_builder.py`
- `tests/r109_real_argos_flask_smoke.py`
- `.github/workflows/ffh-r109-pinned-source-check.yml`

## NOT PROVEN
- GitHub runner test was one process; no real 512 MiB cgroup cap enforced, no Gunicorn master, no concurrency/health-under-load, no long text or multilingual language models.
- A successful synthetic English->Spanish output is not scientific or safety review.
- Release requires R110 and further multilingual/operational validation, independent code and license review, rollback.
- Do not merge to main: Render automatically deploys it.

## Follow-up
R110 is the isolated 512 MiB Docker cgroup/Gunicorn test branch:
https://github.com/easy123dcavers-ctrl/ffh-translation-service/tree/ffh-r110-memory-cgroup-staging-20261016
