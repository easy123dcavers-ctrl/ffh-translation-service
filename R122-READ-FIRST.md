# FFH R122 — START HERE — Restart reliability / 512MiB evidence
Date: 2026-10-16. **Experimental translation service engineering only, NOT whole FFH website.**
Branch `ffh-r122b-quiescent-restart-20261016`.

## Verified R122 results — three distinct outcomes, no hiding failures
| Run | Scenario | Result |
|---|---|---|
| [R122 diagnostic](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38858513619) | Gunicorn automatic max-requests=24, standard keepalive 2 | **FAIL**: ConnectionResetError after 150 items, 281.89 MiB peak, no OOM |
| Same R122 diagnostic | max-requests=24, Connection: close, Gunicorn keepalive 0 | **FAIL**: ConnectionResetError after 150 items, 282.71 MiB peak, no OOM |
| [R122b controlled master](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38858738514) | Disabled auto recycling (max-requests=0), FOUR separate master lifecycles, only shutdown when guarded file lock idle | **PASS isolated behavior+resource gates**: 350/350 batch-item results, 14/14 deliberate HTTP 429, peak 280.98 MiB, 45.12% reserve, zero OOM |

The 128.53-second R122b test performed **three explicitly scheduled master restarts** between four lifecycles. Each distinct master started exactly one Gunicorn worker; no automatic worker restarts happened. All guarded batches completed and the file lock was free before each controlled shutdown. Two legacy routes remained quarantined (410) and unauthorized bearer failed (401) in all four lifecycles. 322 outputs were provisional, 28 were held without drafts, zero human approvals or production writes.

Other performance details: worst health response 0.0808 seconds while translating; p95 measured in this tiny synthetic sample 0.0049 seconds; restart cold times in pre-built container ~0.75–0.80 seconds, NOT initial deployment/cold model-install times. German Argos en→de, batch1/beam4, pinned test Argos source, one model, 1 CPU, hard 512 MiB cgroup, offline runtime, 1 worker/2 threads, no cache, synthetic texts only.

## Root-cause evidence — do not overstate
Gunicorn gthread source in v23 sets `self.alive=False` and force-closes a connection when `nr>=max_requests`. Earlier R121d Gunicorn logs show `Autorestarting worker after current request` immediately before the client TCP reset. R122 confirms that keepalive changes do NOT prevent the reset. This strongly implicates requests arriving during worker turnover but it does NOT establish a complete upstream bug diagnosis or prove all failure paths.

## Why the controlled restart is NOT ready for members
The R122b driver deliberately **does not send new requests during the gap between stopping the master and starting the next**. It is NOT zero downtime, has no deployed traffic drain/readiness broker and has not proved safe behavior on unexpected crashes or lost connections. A production migration must route members via a trusted server-side FFH auth broker that stops new admission, drains accepted requests, returns explicit 503/Retry-After to new arrivals, then restarts and resumes when truly healthy. Do not send shared service secrets to public Netlify JS. In a 512MiB cgroup, do not overlap two warm model copies without testing; overlap could OOM.

R122b deliberately sets `--max-requests=0`. This is safe only as part of a **verified independent idle restart policy and sustained RSS monitoring**; otherwise model memory accumulation can recur. Never deploy this flag on the live service just because an isolated 128-second test passed. No owned production automation implements safe idle restart today.

## Code + exact branch artifacts
- `tests/r122_gthread_transport.py`, `tests/r122.Dockerfile`, `.github/workflows/ffh-r122-transport.yml` on diagnostic branch `ffh-r122-worker-recycle-transport-20261016`.
- `tests/r122b_quiescent_master_restart.py`, `tests/r122b.Dockerfile`, `.github/workflows/ffh-r122b-quiescent.yml` on passing R122b branch.
- `R122-ENGINEERING-DECISION.md` documents observed Gunicorn implementation and required gates.
- The handoff ZIP preserves both failed artifact summaries and Gunicorn logs and the successful R122b summary + four logs. GitHub artifacts have only 3-day native retention: retain the handoff ZIP safely.

## Next acceptance gates (R123)
1. Build a test-only **trusted broker or model service readiness/draining gateway**, with no FFH Member secrets, that gives explicit fail-closed 503 before accepting new work, confirms zero accepted in-flight requests and admission file lock idle, schedules idle master restart and resumes only on /health success. Simulate clients arriving *during* the restart gap; they must receive an explicit response rather than a hidden TCP reset.
2. Exercise simulated fault injection (SIGTERM, SIGKILL, unexpected worker crash, restart timeout, 429, 503) and exact client retry/idempotency semantics, but do not automatically repeat failed/unknown accepted requests.
3. Expand duration and target coverage, monitor memory drift. Enforce 512 MiB hard limit + >=15% headroom, zero OOM and live health p95; audit one-model-per-process assumption.
4. Design actual FFH Member/Owner authorization server-side; the staging bearer is NOT member auth and legacy routes are protected only under opt-in staging flags. Live Render's original one-thread command differs from test configuration.
5. Independently audit modified Argos source, vulnerable/transitive libraries, licenses and direct model package archive SHA **before installation**. Post-install tree hashes are insufficient.
6. Qualified multilingual fermentation-safety and translation review for all nine language mappings, including fil→tl, zh-Hans→zh, Arabic RTL and numeric/units; no machine publication or Reviewed-state bypass.
7. Owner-approved release plan, monitor and rollback. Never merge experimental branches to `main` (Render auto-deploys), modify Supabase or deploy Netlify as a test.

**Current production release decision: HOLD.** No Render changes, no Netlify credits spent, no Supabase writes, no human approvals. These are engineering experiments, not publication or public service security authorization.
