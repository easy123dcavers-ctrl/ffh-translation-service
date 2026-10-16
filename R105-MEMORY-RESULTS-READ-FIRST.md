# FFH R103–R106 LOW-MEMORY TRANSLATION HANDOFF (2026-10-16)

## STOP / PRODUCTION STATUS
Production Render, Netlify and Supabase: UNCHANGED. Do not deploy, merge, ingest, approve or change production configuration from this packet. FFH Render auto-deploys MAIN; all work here stays on experimental branches. Only EN->ES synthetic texts were measured.

## Confirmed Render failure diagnosis (read-only Render inspection)
Service `ffh-translation-service` on free plan has a 512 MiB memory limit and 1 Gunicorn worker/1 thread in deployed service. October 13 Render events include out-of-memory kills with memoryLimit=512Mi and failed HTTP health checks timed out after five seconds. This is an observed production reliability defect; memory metrics endpoint returned no current data points.

## R103: four Argos 1.11.0 profiles in fresh test processes
20 invented EN->ES strings per profile. Mechanical flags=0 and exact output differences vs baseline=0 for all 3 variants on each worker. Note these checks do not establish linguistic or food safety accuracy.

| Profile | A peak MiB | B peak MiB |
|---|---:|---:|
| Default | 909.02 | 914.71 |
| MINISBD | 750.69 | 757.18 |
| MINISBD + int8 + restricted threads/batch | 748.86 | 753.37 |
| Default chunking + int8 | 908.72 | 913.84 |

A: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38830821926
B: https://github.com/KatsuraFukuryu/ffh-translation-tests/actions/runs/38830825510

## R104: dependency removal WITHOUT source modifications — FAILED (informative)
Attempting to remove the Stanza dependency alone or with PyTorch made pinned Argos 1.11.0 fail to import. Traceback identified a direct `import stanza` in `argostranslate/sbd.py`. Do not simply remove installed packages in production.
A: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38831223052
B: https://github.com/KatsuraFukuryu/ffh-translation-tests/actions/runs/38831226913

## R105: DISPOSABLE test-runner-only patch/probe — PASSED
R105 temporarily changed the eager Stanza import in the installed package in a disposable GitHub runner, allowed MiniSBD only, and measured 20 invented test texts before/after.

| Setup | A peak MiB | B peak MiB |
|---|---:|---:|
| Original dependencies | 750.48 | 750.42 |
| Bypass eager Stanza import, keep heavy packages | 724.13 | n/a |
| Bypass eager import AND remove Stanza and PyTorch | n/a | 244.21 |

The B output exactly matched its unchanged full-dependency baseline for all 20 invented inputs. No mechanical number flags were detected. B's 244.21 MiB is a **proof of feasibility**, not production certification. A retained heavy dependencies and still loaded Torch, explaining the limited reduction.

A: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38831598452
B: https://github.com/KatsuraFukuryu/ffh-translation-tests/actions/runs/38831602671

## R106: planned localhost Flask/Gunicorn integration — NOT RUN
The source code for a localhost-only test is available at `tests/r106_localhost_service.py` on `ffh-r106-local-service-memory-20261016`. It checks /health, /translate, /translate-batch, concurrent health while translating, invalid batch limits, and samples Gunicorn master and worker process high-water memory. The proposed automated workflow creation was blocked, so this test has NOT BEEN EXECUTED. There is no verified Flask/Gunicorn memory total or health-check result for the low-memory configuration.

## Mandatory next engineering work
1. Replace the disposable third-party edit and unsupported dependency removal with a maintainable, version-pinned, license-compliant lightweight build/fork or supported upstream option. Review its supply-chain and maintenance risk.
2. Test all nine site languages, actual input lengths, multiple sentence boundaries, numeric/unit/placeholder preservation, and human safety/linguistic QA on non-production data. EN->ES 20-string parity is insufficient.
3. Verify in a memory-constrained (512 MiB or stricter) replica including Flask, Gunicorn, health endpoint, 25-item batches, restarts, crashes and concurrent requests. Leave headroom; 244 MiB alone is not an end-to-end measurement.
4. Review request confidentiality. The optional R102 global process-local cache is OFF by default and not approved for members' private strings.
5. Verify precise path and date of FFH models and installation behavior, avoid unbounded model counts and automatic per-request model downloads; preserve all Supabase translation safety gates and reviewed-state immutability.
6. Add independent review and rollback instructions before requesting owner permission for a controlled deploy. NEVER auto-deploy from these branches.
7. GitHub Actions is for isolated CI tests, not continuous production translation workloads.

## Current decision
R105 proves one very promising memory-optimization direction. R106 production-shaped integration and a supported dependency build remain BLOCKING. No release approval.
