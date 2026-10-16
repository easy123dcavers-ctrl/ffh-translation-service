# FFH R131 — zero-retraining engineering checkpoint

Date: 2026-10-17. Read alongside `R130-READ-FIRST.md`, `R121-BROKER-CONTRACT-DESIGN-ONLY.md`, and R129 handoff ZIP.

## New verified finding (R129 memory-attribution real-model test)

GitHub Actions run **38941241901** completed SUCCESS on the isolated R129 branch:
https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38941241901

- **ALL NINE** pinned Argos models loaded, switched serially, and handled one actual guarded batch each.
- 225 synthetic fixture items total, 9 separate Gunicorn master lifecycles; 0 OOM kills.
- **283.79 MiB** total cgroup peak, **44.57%** RAM reserve under **512 MiB**, with **0.1 CPU** enforced.
- Duration **753.3 seconds** (~12.6 min), **one circuit**, not 30 minutes. Do not call this release certification.
- No runtime source/model download; every installed model tree SHA-256-verified in Docker BUILD against R113-derived baselines. R129 diagnostic OMITTED repeated full-tree SHA-256 walks during each runtime model switch.
- The previous R129 experiment that rehashed model files just before Argos load hit 459.51 MiB (10.25% spare) with 25 items; 5-item variant 461.37 MiB (9.89% spare). This is strong *circumstantial experimental* support that page-cache pressure due to verification overlapped with model runtime memory. Not yet isolated proof of causation for all variables.
- R129 validation is experimental; model package publisher-level provenance and license review remain unresolved.

## Owner's binding acceptance policy

Owner said: **"10% is fine if it holds"**. Thus R130/R131 experimental minimum is >=10% headroom **for the whole 30min test**, including all peak memory; 20% remains the original stricter engineering preference, and passing it would be better.

**No authority to change production, automatically approve translated text, use unsafe safety-critical content, raise memory/CPU cap, or deploy.**

## R130 vs R131

- R130 long-soak run 38942467399 uses original per-switch full-tree rehash with 10% headroom, and remains a separate historical baseline test:
  https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38942467399
- R131 long-soak run on this branch **removes only repeat runtime rehashing**, retaining Docker build-time SHA verification, all 9 real model packages, exact RAM byte gate and 0.1 CPU, 30min monotonic duration, >=2 complete circuits, single worker lifecycle, locked staging-only gateway, explicit 401/410/429/503 behavior, and one intentional SIGKILL that must yield 502 outcome UNKNOWN (no automatic replay).
  https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38943614131

## Code/change boundaries

- R131 generator: `r131/prepare_endurance.py`, imports existing pinned R130/R129 generator and replaces **one** per-switch `verify(target,p,baselines)` call with a lookup against the installed-model manifest that was verified in the Docker build.
- R131 tests: `tests/test_r131_generator.py`.
- Disposable CI workflow: `.github/workflows/ffh-r131-build-verified-endurance.yml`.
- Previous R130 exact 10% gate and historical 20% gate remain separate untouched files.

## What still blocks publication

1. **Real R131 outcome** must show >=1800 seconds, >=2 full nine-language circuits, exact <=460.8MiB cgroup peak, zero OOM kills, no unplanned worker restart, successful deliberate SIGKILL/UNKNOWN behavior, authenticated synthetic boundary, and isolation. A passing image BUILD alone is insufficient.
2. **Real Member auth broker**, protected translation queue, quotas and revocation policy not implemented. R121 is design only.
3. **Supabase production jobs**: last read-only count 131 completed, 615 failed, 156 pending; do NOT replay these without request-contract repair and idempotent reconciliation. No production SQL write or secret in these tests.
4. **Language QA/fermentation safety** must be independently approved; Argos drafts remain provisional/held, never reviewed/published automatically.
5. **Netlify website source parity and staging Android tests** still not verified. No production deployment.

## Operational instructions

- Check actual GH Actions run conclusion and summarized full-metric artifact. Never call success if no machine-readable report.
- If R131 fails, preserve exact stage, peak, OOM and crash response; investigate one failure at a time without loosening caps automatically.
- Do not touch GitHub `main` (Render auto-deploys `main`).
- Return one cumulative FFH ZIP when tests are resolved, including source pins, evidence, and an updated READ-FIRST ticket.
