# FFH R111 — Sustained, offline 512 MiB translator stress test
Date: 2026-10-16. Test branch: `ffh-r111-sustained-offline-stress-20261016`.
Production: **UNMODIFIED**. This report documents synthetic EN→ES-only experimental evidence.

## Verified GitHub result
**PASS** https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38837736796

Real Docker cgroup `memory.max=512MiB`, `--memory-swap=512m`, `--cpus=1`, runtime `--network none`. Experimental pinned Argos 1.11.0+ffhlite1 build, offline preinstalled Argos EN→ES and MiniSBD EN models, Flask/Gunicorn one worker with two threads, translation cache OFF.

Two separately started Gunicorn server processes (`pid 7`, then `pid 24`) completed two 25-item batches each: **100/100 successful invented batch translations**. Across those two starts, **6 long/multi-paragraph translation requests passed**. No empty outputs, 0 automatic numeric preservation mismatches on the tested fixtures, 0 model errors recorded, health HTTP 200 during an active translation batch, invalid JSON and >25 items rejected. Both server rounds terminated successfully.

Memory cgroup `memory.peak = 219.39 MiB`, headroom `57.15%`; changes in `oom_kill=0` and `oom=0`. Total active stress ~47.41 seconds. Gunicorn restart startup times 0.746s and 0.737s in this **already-built, warmed container**, NOT initial Render deploy cold-start timings. Batch translation times: 9.740, 9.229, 10.037, 10.008s. Slowest health response while batch active 0.129s in first round, 0.005s in second.

## Reproducibility
- `tests/r111_sustained_service.py` — loopback-only live HTTP stress; two server instances, 4 batches, longer invented paragraphs, health-under-load and cgroup memory verification.
- `tests/r111.Dockerfile` — lightweight build, Argos EN→ES and MiniSBD EN model preinstall.
- `.github/workflows/ffh-r111-sustained-512m.yml` — isolated branch-only CI, Docker runtime network disabled, uploads artifact `r111-synthetic-512m-restart-stress` (3-day retention).
- It reuses the original R109 source-pinned builder and R110 MiniSBD prefetch logic.

## Limitations / release gates
This is **not production release approval**. Requires independent source/license/supply-chain review, exact EN→ES model artifact pinning, longer endurance/load and restart in Render-like environment, all nine language model tests one model per memory-capped service, privacy/rate limits/input-size controls, accessibility and safety-content linguistic review, and explicit owner-controlled deployment approval. Do NOT merge a test branch into `main` (auto-deploy), deploy Netlify, ingest translations, or bypass Supabase review gates. FFH human approved translations and safety-protected sources must remain authoritative.
