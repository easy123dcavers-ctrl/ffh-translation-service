# FFH R132 — zero-retraining Main Coordinator checkpoint

Date: 2026-10-17. This is a **disposable testing branch**, not approval to deploy.

## Critical current finding: 429 race in experimental gateway

GitHub Actions R130 run https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38942467399 ended FAILURE at 887.31 sec (14.8 minutes).
- Real nine-model cycling had completed one full circuit and begun the second: 725 synthetic fixture items processed across 15 model stages; no OOM kills.
- Peak cgroup memory **290.0 MiB**, **43.36% headroom**, 512MiB limit, CPU quota **10000/100000 = 0.1 core**. RAM was NOT the blocker.
- Error: **"Overlapping translation not rejected"** on German stage 2. The prior gateway's `Readiness.begin()` admitted multiple concurrent calls and delegated "busy 429" timing to the model backend; a fixed 85ms sleep did not establish an atomic overlap, so results were race-prone.
- This is a real design weakness (no gateway single-flight) plus an unreliable test assertion. Do not claim R130 endurance success.

## R132 correction (this branch only)

- `tests/r125_serial_gateway.py` changed **only here**, NOT on Render main or other legacy branches.
  - Gateway readiness now uses a condition-protected **single atomic active slot**.
  - Authenticated calls arriving while one is active receive **HTTP 429** and `Retry-After: 2`, never forwarded to backend; when draining, they get **503**. Unauthorized calls stay **401**; legacy route stays **410**.
  - A synthetic loopback-only **bounded TCP listen backlog = 64** lets 16 simultaneous contenders receive explicit busy status instead of socket resets at Python's default backlog of five. No actual public exposure and NO bypass of later broker quotas.
- `tests/test_r132_singleflight_gateway.py`: four behavioral tests plus one backlog contract for atomic 429, burst requests, auth, and draining under a deliberately blocked synthetic backend.
- `r132/prepare_endurance.py`: inherits pinned R125F->R129->R130->R131 generator; replaces one **fixed 85ms sleep** with a bounded actual admission observation before the competing-call check. CPU, duration, memory gates are untouched.
- `tests/test_r132_generator.py`: verifies source/gates remain intact.
- `.github/workflows/ffh-r132-singleflight-endurance.yml`: CI tests + pinned upstream verification + all nine model files SHA256 verified in Docker build + real 1800sec, 512MiB, 0.1 CPU run + zero OOM and >=10% headroom + two circuits + deliberate SIGKILL unknown outcome. **DO NOT construe PASS as production release certification**.

## External evidence status

- R129 no-runtime-rehash shorter test: **SUCCESS**, 225 real synthetic items, 9 model targets, 753.3s, 283.79MiB peak, 44.57% reserve, 0 OOM.
  https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38941241901
- R130 original-rehash 30min: **FAILED** after 887.31s on concurrency test; memory stayed safe.
  https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38942467399
- R131 30-minute build-verified, no runtime rehash: **last observed IN PROGRESS**. Confirm actual status before reporting results.
  https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38943614131
- R132 first run 38946058649: **FAILED** during burst test because default Python server listen backlog 5 reset one of 16 connections. Three other singleflight tests passed; generator tests passed. No real-model run started on that attempt.
- R132 second run 38946255555: **last observed IN PROGRESS**, generator and gateway tests passed, building real model image.
  https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38946255555

## No production authority

- Leave GitHub `main` at previously observed `5f8bcecba92653f653ef4514c6fcf32d9d6efbe9`; Render service auto-deploys from main.
- Zero Netlify deployments, zero Supabase updates, zero Render changes.
- No translation approvals, direct or indirect. Machine candidates are provisional/held; real member authorization broker is still DESIGN ONLY (R121).
- Live Supabase job backlog at last read-only checkpoint: 131 completed, 615 failed, 156 pending. Do not retry jobs until HTTP target mismatch and ambiguous outcomes are reconciled.
- Owner authorization: **"10% is fine if it holds"**. Require >=10% reserve throughout verified full real 30-minute test, and zero OOM; do not loosen 512MiB or 0.1CPU or use average to conceal transient peaks.
- Further blockers: independent security and scientific/translation QA, package archive provenance, member token verification/revocation/rate limits, staging Android and source parity, safe rollback/approval.

## Immediate next task

1. Read actual R131/R132 GitHub Actions job status and `summary.json` (if emitted). Preserve any failures and report reason, stage, cgroup peak, duration, OOM, and crash witness.
2. If R132 passes, move to separate isolated real Member broker prototype with trusted Supabase Auth JWT verification, quotas and audited authorization; NO production write or deploy without new release gate.
3. If R132 fails, fix only the demonstrated issue with a new isolated test; do not repeat large builds for no new hypothesis.
4. Return ONE cumulative handoff artifact with exact code and evidence; the canonical code is on this branch.
