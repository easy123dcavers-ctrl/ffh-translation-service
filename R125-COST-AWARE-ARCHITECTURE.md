# FFH R125 — cost-aware architecture decision (DESIGN ONLY, NOT IMPLEMENTED)
Date 2026-10-16. FFH translation service experimental code; production unchanged.

## Measured in isolated GitHub Actions
R125c real nine-model experiment https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38877486665: **PASS**.
- One Docker test image contained nine Argos EN-target model trees ON DISK; the image's Docker-reported *uncompressed* size was **2,464,701,718 bytes (2.46 GB)**. This is NOT a compressed registry-transfer size, a Netlify artifact size, or proof of compatibility with every Render deploy mode.
- Models were selected ONLY after the previous model's Gunicorn master process exited and accepted requests drained, with model-file hashes matching previously observed installation trees. Actual sequence `es→ko→fr→vi→ja→de→ar→tl→zh` (9 stages/8 transitions). One active backend at a time, never nine simultaneously loaded into RAM.
- Hard Docker cgroup 512 MiB and 1 CPU, 9 fresh master lifecycles, 800 synthetic item occurrences, 32 successful 25-item batches, 32/32 overload 429s, 9 wrong-loaded-target 503s, 19 during-gap/initial 503s, 321 held and 479 provisional results, zero approvals/writes, zero OOM kills, zero gateway transport errors.
- Peak **289.51 MiB, 43.46% headroom**, minimum requirement 20% reserve; the observed-model tree digest equality is post-install repeatability, NOT model publisher archive authentication.
- This is a short synthetic benchmark (260.48 seconds) under a resource allowance DIFFERENT from the live Render Free service. It is not evidence of sustained uptime, actual Render deploy feasibility, public user identity, linguistic accuracy, or route safety.
- The live Render service was read-only inspected; it remains `plan:free`, Python build `pip install -r requirements.txt && python install_models.py`, original startup `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 1 --timeout 180 app:app`, auto-deploy on `main`, one instance. Experimental R125 code has NOT been deployed or merged.

## Independent repeatability
https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38878483569
**Check latest workflow verdict before asserting repeat PASS.** The second job is a fresh nine-model image build and all nine independent process switches under the SAME hard gate.

## Actual Render Free concerns (verify against current official docs)
- Render's Free web service is listed at **0.1 CPU, 512 MB RAM**. R125c used 1 CPU and a 512MiB test cgroup. Thus throughput, timeouts and exact decimal memory limit are NOT production-equivalent, even with excellent cgroup headroom.
- Render free services spin down after 15 minutes of no inbound traffic; waking may take about one minute. They have an ephemeral filesystem, do not support a persistent disk, and may restart at any time. A strategy that downloads models into writable runtime storage risks losing them on every spin-down/restart. Building model packages into an image may avoid runtime download, but deployment image size, build time and startup behavior must be measured.
- Official docs: https://render.com/docs/free , https://render.com/docs/compute-plans , https://render.com/docs/deploying-an-image .
- Separate R125e CPU probe under `--cpus 0.1` with real EN→ES synthetic workload, comparing one and two Gunicorn threads: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38878733730 . Inspect outcome independently; this is NOT a prod deploy.

## Recommended FFH low-cost architecture (NOT YET AUTHORIZED/BUILT)
1. All real members browsing the site should receive **reviewed translations from Supabase/public translation bundles**, with canonical English as safe reference. A live browser page must not depend on the free-tier model service waking up and switching targets.
2. New English content additions enter a **translation candidate queue**, not a direct reviewed/public translation. Staff-side, authenticated backend broker processes bounded batches into provisional drafts/holds using one model resident at a time. Explicit protected/safety-critical source classification and human approval gates remain unchanged.
3. When a model is unavailable or busy, broker returns explicit 503/Retry-After and queues valid workload for later, rather than dropping, silently replaying unknown results, or making the frontend user wait. Protect user-private text and never expose service bearer or Supabase service_role in browser JS.
4. A real FFH Auth JWT/permissions broker with per-user quotas and authorization checks is required; the test shared bearer is not sufficient. The old unguarded /translate routes are outside stage controls in production and MUST be secured/retired before exposing any live translator.
5. No automatic promotion to Reviewed/public output. Independent fluent + fermentation-science QA is required for all nine languages and safety-protected sources, including fil→tl, zh-Hans→zh and Arabic RTL.
6. Maintain exact >=20% peak headroom with zero OOM for each model and on repeated nine-target switches, **AND** test free-tier 0.1CPU performance, real Render cold spins, unexpected termination, 30+ minute workloads and proper retries before release.
7. On successful independent security and food-safety signoff, the Owner decides a guarded staged deployment and rollback plan with minimal Netlify credit usage. NEVER merge test branches into production auto-deployed main as an experiment.

## Seven workstreams remain
(1) production-equivalent, longer stress/cold recovery + multi-model orchestration;
(2) actual FFH Member Auth broker and quotas;
(3) legacy endpoint migration;
(4) supply-chain/security/privacy and licensing;
(5) independent multilingual fermentation-science QA;
(6) translation-memory and publication governance integration;
(7) owner-approved end-to-end staged launch and rollback.

**PRODUCTION RELEASE: HOLD.** No Render/Netlify/Supabase changes or automatic model approvals.
