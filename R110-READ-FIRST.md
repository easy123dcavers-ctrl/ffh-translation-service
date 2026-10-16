# R110 — 512 MiB offline Gunicorn validation — READ FIRST
Date: 2026-10-16. Branch: ffh-r110-memory-cgroup-staging-20261016.

## VERIFIED PASS (2nd attempt)
GitHub Actions: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38836986419
Artifact: `r110-512m-cgroup-evidence` (retention 3 days).
- **Docker enforced memory.max = 512 MiB**, memory-swap limited to 512 MiB; runtime networking OFF.
- Actual Argos English→Spanish model loaded, Gunicorn 1 worker and 2 threads, live Flask HTTP on container loopback.
- **cgroup memory.peak = 220.34 MiB; headroom 56.96%; oom_kill = 0**.
- Conservative summed observed process VmHWM = 272.60 MiB (master 22.95, worker 249.65), also below cap. Cgroup accounted pages differ from RSS sums.
- Single translation HTTP 200 in 0.404s.
- Exactly 25 synthetic batch entries all OK: HTTP 200; 5.968s.
- Health HTTP 200 **while batch still running**, observed 0.006s.
- Invalid JSON root, missing target under current contract, oversized batch -> 400.
- Health before and after -> 200. Elapsed smoke ~8.48s.
- Cache OFF; no private FFH text, no production writes, no Netlify deployment.
- English MiniSBD sentence-splitting model **pre-installed into Docker image** during build, integrity SHA256 `6fa9f3a3b201687bd43e329b2b0736789efc97b37883b5b759b31988dca9f353`; no runtime model downloads.

## FAILURE HANDLED (1st attempt)
https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38836634216
Original Docker test had networking disabled but failed because MiniSBD tried to download its EN model at first translation request. Health checks still passed and no OOM occurred. Inspectable error: `urllib.error.URLError: Temporary failure in name resolution` from `minisbd.models.get_model_file`. Fix: build-time `tests/r110_prefetch_minisbd.py`, which explicitly downloads and checks the model before the runtime network is disabled. **Do not remove this step**.

## SOURCE/REPRODUCIBILITY
- `tools/r109_prepare_lightweight_source.py`: checks immutable Argos upstream v1.11.0 commit `63b84ecb46c740c7a7c066d58636434d3e893ebf`, produces attributed test distribution `1.11.0+ffhlite1` with optional Stanza import and no compulsory stanza/torch dependency.
- `tests/r110.Dockerfile`, `tests/r110_prefetch_minisbd.py`, `tests/r110_cgroup_assert.py`, `tests/r106_localhost_service.py`.
- `.github/workflows/ffh-r110-memory-isolation.yml` does NOT deploy; only runs on R110 experimental branch.

## PRODUCTION RELEASE GATE — NOT YET APPROVED
The current success is one **English→Spanish, short-text, 25-item, one worker/two thread** synthetic trial. Required:
1. Independent security/packaging review, pinned translation model checksum and update policy; test distribution is a custom source build, not officially supported Argos release.
2. Repeat stress, long/multi-paragraph text, restart and cold start, production-equivalent environment and worst-case memory headroom; verify all FFH languages individually, not all models in one 512 MiB instance.
3. Genuine linguistic/safety assessment of fermentation terms, numbers, temperatures, units, placeholders, RTL, and safety-gated sources.
4. Member data protection, rate limits and request-size controls; any R102 cache stays disabled until separate privacy review.
5. Explicit owner approval, controlled rollback and monitoring before merging any changes to `main` (which auto-deploys Render). Never modify Supabase/Netlify as part of this trial.

## Summary
**R110 experimental resource/health acceptance: PASS. FFH production release: HOLD.**
