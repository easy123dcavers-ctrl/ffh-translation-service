# FFH R135 — read first: full real 30-minute nine-language evidence and conservative follow-up
Date: 2026-10-17. GitHub experiment branch only. Main Coordinator zero-retraining handoff.

## CRITICAL VERIFIED MILESTONE — R131 PASSED FULL ENDURANCE

GitHub Actions https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38943614131
**Completed SUCCESS with independent post-run strict resource gate.**
Machine-readable reported:
- status: PASS_BOUNDED_NINE_MODEL_SWITCH_RESOURCE_ONLY.
- Wall time: **2340.69 seconds (39.01 minutes)**, requested >=1800 seconds.
- Complete nine-target cycles: **2**, and 19 separate model stages including intentional crash witness.
- Real Argos translated/held fixture items: **775**; all synthetic, 0 production writes, 0 human approvals.
- **285.12 MiB peak** out of exact 512 MiB, **44.31% memory reserve**, **0 OOM kills**; cgroup CPU 10000/100000 = 0.1 core.
- All 9 models en->(es,ko,fr,vi,ja,de,ar,tl,zh) used one-at-a-time, pinned model-file trees SHA256 verified at Docker build. No runtime full-tree rehash, no runtime network.
- **31 busy HTTP 429** challenges; no automatic unintended worker restarts; successful real intentional SIGKILL with HTTP 502 UNKNOWN non-retryable.
- **Resource-only experimental success**, *not* production deploy approval or secure member authentication sign-off. R131 gateway still admitted concurrent requests until backend lock enforced 429; separate R132 synthetic tests demonstrated the need for stronger deterministic atomic admission.

## WHY THIS R135 BRANCH EXISTS

- R130 with original gateway failed timing-sensitive busy concurrency assertion at 887.31s, peak 290.0 MiB, 43.36% free. R131 successfully ran full 39m as described.
- R132 introduced **gateway-level atomic single-flight** + bounded loopback listen backlog, passed staged concurrency unit tests. But its real-model benchmark saw **495.07 MiB peak (3.31% reserve)** on Korean within 107s, failing owner minimum 10%. Thus integration+memory repeatability is unresolved.
- R133 short two-target resource diagnostic recorded **256.76 MiB peak / 49.85% reserve**, 125 real fixture items, and verified intentional backend SIGKILL produced UNKNOWN. It failed only an inherited nine-model **German check** inappropriate for a two-language diagnostic. Cgroup memory.stat showed about 210MiB Spanish and 249MiB Korean ANONYMOUS process memory and <1MiB file page cache after inference. Avoid claiming file-cache hashing fully explains intermittent 495MiB spikes.
- Owner accepts **>=10% reserve if it holds**; 512 MiB and 0.1 CPU caps remain hard. Stricter 20% is desirable when feasible.
- R134 tests reduce CTranslate2 Argos batch/beam to **1/1 for all targets** and Gunicorn to one thread. This may affect translation quality/throughput: every candidate stays provisional and needs QA.
- R135 inherits R132 gateway single-flight, pinned source SHA, all nine build SHA model checks, and R134 conservative beam=1/thread=1 settings. CI runs short actual Spanish/Korean preflight in a fresh cgroup **before** the full nine-language >=30min real-model stress, enforcing 10% exact RAM reserve and SIGKILL crash witness both times. Failed preflight cancels long run automatically.

## GITHUB LINKS (READ ACTUAL CURRENT STATUS, NEVER ASSUME PASS)
- R131 confirmed success: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38943614131
- R134 independent conservative es/ko pilot: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38948485566 (last observed running)
- R135 short-gated full workload: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38948743697 (last observed running)
- This branch: https://github.com/easy123dcavers-ctrl/ffh-translation-service/tree/ffh-r135-conservative-endurance-20261017
- R135 local code: r135/prepare_endurance.py, tests/test_r135_generator.py; workflow .github/workflows/ffh-r135-conservative-endurance.yml.
- R134 pilot code: r134/prepare_probe.py, tests/test_r134_generator.py; workflow .github/workflows/ffh-r134-conservative-probe.yml.

## ABSOLUTE SAFETY / GOVERNANCE

DO NOT push to GitHub `main` (auto-deploys Render), deploy Render/Netlify, modify production Supabase, publish/approve machine translations or start production retries. These trials use synthetic text and staging-only bearer, NOT a Member Auth broker.
Production Supabase last read-only snapshot: 131 completed, 615 failed, 156 pending translation jobs (771 needing safe disposition). No auto replay of unknown HTTP 502 outcomes.
Separate release gates: actual Member JWT verification, revocation and quotas, privacy/redaction, human translation and food-safety review, staged Android search/locale tests, package archive provenance/license, rollback and production source parity.
Never claim resource-only experimental PASS proves live service reliability/production rollout readiness.

## NEXT

1. Read latest R134/R135 workflow results and summary.json artifact. If complete, verify real outputs rather than relying only on green CI status.
2. If R135 long-run passes >=1800s / nine-target >=2 cycles / no OOM / exact 10% headroom / 1 SIGKILL UNKNOWN / deterministic singleflight 429, freeze experiment and plan broker security gate, not immediate deployment.
3. If R134 or R135 fails, preserve cgroup memory and exact failure without relaxing resources. The earlier full R131 SUCCESS is immutable historic evidence, not evidence that the new code version passed.
4. Return one cumulative ZIP with source pins, automated regression results and MC instructions.
