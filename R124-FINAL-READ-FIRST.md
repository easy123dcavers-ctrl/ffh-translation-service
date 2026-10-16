# FFH R124 FINAL — All nine isolated language models passed two 20%-headroom tests
2026-10-16. **ENGINEERING GATE ONLY. PRODUCTION RELEASE: HOLD.**

## What is now verified
Every one of nine FFH target-language mappings has a selected profile with **two separate successful tests** using real lightweight Argos under a **hard 512 MiB cgroup with >=20% spare RAM** (max peak 409.6 MiB, zero OOM kills). Each test isolated **one target model per container**, ran 4 Gunicorn master lifecycles with 3 controlled restarts and an always-on loopback gateway, enforced bearer-authenticated guarded translation, 429 admission, 503 restart gaps, and no auto-approved outputs or production writes. This DOES NOT imply 9 language models fit into one 512 MiB running service.

| FFH target (Argos code) | Selected batch / beam | Two observed headroom results |
|---|---|---|
| German (de) | **1 / 2** | **44.56%, 45.10%** |
| Arabic (ar) | 8 / 4 | 56.82%, 55.93% |
| Spanish (es) | 1 / 4 | 56.84%, 57.08% |
| French (fr) | 8 / 4 | 56.60%, 58.43% |
| Japanese (ja) | 8 / 4 | 48.68%, 46.60% |
| Korean (ko) | **1 / 2** | **49.88%, 50.09%** |
| Filipino/Tagalog (tl) | 1 / 4 | 57.23%, 58.60% |
| Vietnamese (vi) | **1 / 2** | **60.20%, 60.74%** |
| Chinese model (zh) | 8 / 4 | 57.90%, 57.45% |

## FAILURES kept as first-class evidence
- German batch1/beam4: two cold first-batch 512 MiB OOM kills in R123H. Replaced with batch1/beam2; two passes.
- Korean batch1/beam4: first 257.90 MiB PASS, repeat **499.25 MiB (2.49% headroom) HOLD**. Replaced with batch1/beam2, two passes.
- Vietnamese batch8/beam4: first 205.50 MiB PASS, repeat **446.13 MiB (12.86% headroom) HOLD**. Vietnamese batch1/beam4 first 209.82 MiB PASS, repeat **446.14 MiB (12.86% headroom) HOLD**. Replaced with batch1/beam2, two passes. An optional single batch1/beam1 experiment passed 203.61 MiB but is NOT a quality-reviewed preference.
- R124 initial workflow 38864512811 failed because a test-runner allowlist wrongly restricted targets to de/ko, and the ES post-install tree baseline was not yet recorded. Corrected without lowering resource gates.
- **Never erase these failures or assume two short PASS trials guarantee 30-minute memory behavior.**

## Exact reproducibility
- Earlier German R123H: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38863208567 and https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38863598097
- Seven initial other-language passes: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38864857101
- Spanish observed first post-install bytes (NOT publisher trust): https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38864824281 ; second fresh image/first resource pass: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38865037536
- R124 repeat initial settings: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38865724627 — workflow **FAIL** only Korean and Vietnamese 20% memory acceptance, six others PASS.
- R124b alternative low-memory candidates: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38866447221 — 4/4 CI PASS.
- R124b KO repeat/VI failed repeat: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38866878143 — Korean PASS, Vietnamese beam4 HOLD.
- R124c Vietnamese selected beam2 repeat: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38867313914 — both beam2 repeat and beam1 standby PASS.
- Code from two isolated branches `ffh-r124-eight-language-20pct-20261016`, `ffh-r124b-korean-vietnamese-headroom20-20261016` and current `ffh-r124c-vietnamese-headroom20-20261016`. Base `ffh-r123h-headroom20-20261016` enforces exact unrounded peak bytes <= 80% of 512MiB and no OOM.

All raw CI summary.json and Gunicorn logs for selected and rejected profiles are preserved in **FFH_TRANSLATOR_MC_HANDOFF_R124_NINE_LANGUAGE_20PCT_2026-10-16.zip**, under `R124-EVIDENCE`; the machine-readable nine-target comparison lives in `R124-REPORT/NINE-LANGUAGE-VERIFIED-2-PASS.csv`. This is a translation-service handoff, NOT the entire FFH site.

## Remainder: 7 independent release workstreams (overall % not measured)
1. **Multi-language operation and endurance:** one free 512 MiB service cannot be presumed to keep all nine models loaded. Build and test safe on-demand model routing/loading or a separate resource-approved dispatch architecture; 30+ minute cold/warm reliability, crash, memory drift, long texts, queueing, unknown-result handling.
2. **Real FFH member authorization:** trusted server-side JWT/session validation, roles, rate limits and quotas; a stage bearer must never be embedded in Netlify JavaScript.
3. **Legacy API migration:** both current `/translate` endpoints are not protected by the new staging gates in live production. Audited route retirement, retry UX, Android and rollback required.
4. **Supply-chain/privacy:** publisher-authenticated model archive checksum before install, model licenses, Python dependencies/upstream patch security review, private-text logging/retention controls.
5. **Native-speaker & fermentation-safety QA:** all nine target languages; correct weights, ratios, temperatures, salinity, acidity and safety exclusions; `fil→tl`, `zh-Hans→zh`, Arabic RTL specifically unresolved. Lower beam can change meaning and has not been qualified linguistically.
6. **Approved translation-memory integration:** no machine-generated candidate may self-review, bypass protected safety-source approval or write Reviewed/public content. Live translation row backlog not measured by these test runs.
7. **Owner-controlled staged release and rollback:** production-equivalent Render/Netlify/Supabase dummy-user validation, monitors, rollout/rollback; limit Netlify redeploy credits.

**Current production Render, Netlify and Supabase unchanged. No model-generated outputs approved. DO NOT MERGE EXPERIMENTAL BRANCHES INTO AUTO-DEPLOYED MAIN.**
