# FFH R125 — sequential multilingual switching under 512MiB, MC handoff
Date: 2026-10-16. Scope: translation-service engineering ONLY. **PRODUCTION RELEASE HOLD**.

## Confirmed achievements
- Existing R124: 9/9 target models **each independently** passed the exact 20% RAM reserve in two short real-model runs with one model installed per active service and carefully selected inference settings. This does **not** mean nine models can run together.
- R125 first two-language disk-switch test: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38876195274 — PASS. The staged test image held `en→es` and `en→fr` on DISK, but only a single Gunicorn backend was active at a time, selected via an atomic symlink only after the previous worker exited. 4 master lifecycles ES→FR→ES→FR, **575 synthetic translation-item occurrences**, 23/23 concurrent HTTP 429, 4 wrong-target 503, 9 during-startup/drain 503, peak **228.95MiB (55.28% headroom)**, zero OOM, zero gateway errors and zero approvals/writes. First attempt https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38876004838 FAIL due Python script test import error before any translation; corrected on isolated test branch, preserved as harness failure.
- R125b four-language serial disk-switch test: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38876851383 — PASS. Four model files were installed separately and verified against previous observed-tree SHAs. Actual process sequence ES→KO→FR→VI, profiles ES batch1/beam4, KO 1/2, FR 8/4, VI 1/2, with 4 master lifecycles and no concurrent model processes. **625** synthetic translation-item occurrences, **25/25** overload HTTP 429, 4 wrong-target 503, 9 gateway 503 during drain/startup, peak **255.29MiB (50.14% headroom)**, zero OOM, zero transport error, zero approvals/writes. Test runner's inherited final string `PASS_SINGLE_INSTANCE_TWO_MODEL_SWITCH_RESOURCE_ONLY` is misnamed but the checked `language_sequence`, `models_on_disk`, 4 rounds and CI PASS are authoritative.
- Code branches isolated: `ffh-r125-single-instance-model-switch-20261016`, `ffh-r125b-four-model-switch-20261016`. No merge into Render auto-deploying main.

## R125c nine-model disk test
- Branch: `ffh-r125c-nine-disk-serial-20261016`.
- Workflow: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38877486665
- Tests all 9 known target trees on disk (ES FR KO VI JA DE AR TL ZH), one *resident backend process* at any given time, serial profile settings exactly from R124 (not a nine-model RAM-loaded process). One CPU and hard 512MiB memory + 20% minimum reserve, runtime internet disabled; expected 9 master lifecycles and eight planned switches. The CI is the sole authority for PASS or FAIL; **do not claim it passed until complete**. Record Docker image bytes from build, measured cgroup peak and cold/warm startup times.
- Exactly one source code model process at a time verified by process separation; no real owner/member text, no Netlify/Supabase writes. Model archive SHA is verified against prior OBSERVED post-install tree, **not authentic archive publisher verification**.

## Technical constraints / remaining effort
1. The R125 gateway and orchestrator are loopback-only isolated tests, **NOT a production FFH member broker**, not a multi-tenant secure router, and not an automation controlling live Render. Model switching imposes planned 503 unavailability. Public browser JS MUST NOT contain a shared staging bearer.
2. Even nine models on disk may create a huge image, exceed the free provider's filesystem/deploy constraints, or cause intolerable language-switch delays. Image size and disk benchmark are independent of the 512MiB RAM headroom gate and must be evaluated against verified current Render plan policies before design rollout.
3. Real request-routing availability, backlog/fairness, frequent language switching, starvation, unexpected SIGKILL, 30+ minute cold/long-text/large batch runs, retries and safe unknown-outcome response remain untested.
4. Legacy public `/translate` and `/translate-batch` remain outside staging-only safeguards in production; securing, migrating and retiring these routes is mandatory.
5. Model archive provenance/license before installation, independent dependency and modified source security audits, privacy and log retention policies are still required.
6. All nine outputs are only provisional or HELD. Human language and fermentation-science review, numeric/temperature/salinity holds, Arabic RTL, `fil→tl` and `zh-Hans→zh` mapping must still be QA'd before publication. No automatic human approval, even on success.
7. Owner-controlled staging, monitoring, rollback, cost and mobile UX acceptance required before any production deploy.

## Next MC working style
Work in substantial self-contained isolated tests, preserve failures, provide real measured % and remaining counts; one comprehensive handoff ZIP; never ask the user to deploy Netlify for testing; never touch GitHub main, Supabase production or Render production. Keep exact 20% free RAM as a hard rejection boundary.

**Production Render, Netlify, Supabase unchanged. Zero approvals.**
