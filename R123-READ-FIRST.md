# FFH R123 — READ FIRST — loopback drain gateway and safe planned restart
Date: 2026-10-16. **TEST CODE AND SYNTHETIC INPUTS ONLY.** Translation service engineering, not a complete FFH site archive.
Branch: `ffh-r123-loopback-drain-gateway-20261016`.

## Actual verified result
- Offline regression suite: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38860367383 **PASS 109/109** (11 R123 gateway tests + 98 older FFH translator contract tests). Tests use an invented fake-model HTTP server; verify authenticated proxy, 503 while draining, in-flight completion, non-cacheable responses, 410 legacy rejection, and 502 with UNKNOWN outcome/no auto-replay on backend failure.
- First R123 real-Gunicorn workflow https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38860534838 **FAILED at Python syntax compilation before Docker/model tests**. The indentation mistake in `tests/r123_gateway_real_soak.py` was fixed on the same isolated branch. Do not describe this run as a memory/API failure.
- **Corrected real Argos/Gunicorn workflow:** https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38860672717 **PASS**. Raw summary and four Gunicorn diagnostic logs are preserved in the R123 MC ZIP; GitHub artifact `ffh-r123-real-gateway-evidence` ID 12028219183 (short GitHub artifact retention).

## R123 REAL MODEL measurements
| Measurement | Verified result |
|---|---|
| Target model | One English→German Argos package; inference batch 1, beam 4 |
| Runtime resource limit | Disposable Docker 512 MiB RAM & swap, 1 CPU, offline runtime |
| Master restarts | 3 planned between 4 separate Gunicorn master lifecycles |
| Batch items completed | **350**, across 14 accepted 25-item batches |
| Accepted candidates (provisional only) | **322**, zero human approvals |
| Held candidates, no drafts returned | **28** |
| Deliberately concurrent translation requests rejected | **14 of 14**, HTTP 429 |
| New requests during unavailable/draining intervals | **7**, explicit HTTP 503 (including initial startup and planned gaps) |
| Local proxy-to-backend transport errors | **0** |
| Peak container cgroup memory | **284.62 MiB** |
| Remaining headroom vs 512 MiB | **44.41%** |
| OOM kills | **0** |
| Longest observed active-service health request | **0.0032 seconds** |
| Runtime wall-clock | **126.98 seconds** |

Each master started exactly one Gunicorn worker, with NO automatic `max_requests` recycling. The acceptance file-lock was proved idle at each shutdown. Legacy POST translation routes stayed quarantined in the backend; the always-on test gateway always rejected those paths with HTTP 410. Guarded route access required the randomly provisioned synthetic staging token; no real account token was used. Every guarded output remained held or provisional and cache disabled.

## What R123 implemented
- `tests/r123_readiness_gateway.py`: **stdlib-only loopback gateway** bound to 127.0.0.1, with a thread-safe active-request count; no public-facing endpoint, no persistent queue and no member authentication. An in-flight translation is counted until its upstream response is fully received. Draining flips readiness OFF *before* waiting for active requests to reach zero. New authenticated requests during the gap get explicit HTTP 503 and `Retry-After: 2`. `GET /health` is HTTP 503 while draining. Unexpected backend connection errors produce sanitized HTTP 502 (`translation outcome unknown`, `retryable:false`), change readiness to unavailable, and NEVER automatically replay accepted requests.
- `tests/test_r123_gateway_contract.py`: 11 synthetic-only stdlib unit tests, including draining while an accepted simulated request is still running, 503 during drain, replay refusal on a dead upstream, token validation, input caps, legacy 410 and no-store.
- `tests/r123_gateway_real_soak.py`: 512MiB integration test with actual pinned lightweight Argos and Gunicorn. The gateway stays active across four master lifecycles, returning 503 when the model service is intentionally stopped and 200 health only when it has confirmed backend readiness.
- `tests/r123.Dockerfile`, `.github/workflows/ffh-r123-real-gateway.yml`, `.github/workflows/ffh-r123-offline.yml`: isolated CI and 512MiB container evidence.
- No deployment, merge to `main`, Netlify upload, Render plan change, Supabase ingestion, protected source reclassification, model publication or user/Member text exposure.

## Important limitations — release STILL HOLD
1. R123 gateway is **loopback-only experimental transport code**, not an FFH Member-authenticated, publicly deployed broker. Staging bearer is a shared test credential, NOT FFH Member or Owner Auth; never place a shared secret in publicly shipped Netlify JS.
2. The *real* 512MiB run deliberately did not allow arbitrary requests to start while its backend was being restarted; it sent bounded HTTP test calls to the gateway during gaps and got 503. It did **not** demonstrate zero downtime, horizontal replicas, unexpected SIGKILL reliability, long-lived crash recovery or large untrusted traffic volumes. The offline fake-backend test does exercise a failure resulting in HTTP 502 and fail-closed readiness.
3. A transient crash that occurs WITHOUT an accepted request may leave the gateway's `ready` bit true until a watcher detects it or a forwarded request fails. **No production crash watchdog implemented.** This needs explicit R124 handling.
4. If an accepted request is interrupted, `502 outcome unknown` must not be interpreted as a definitive non-execution. Never blindly resend private content or auto-publish/approve a translation.
5. Resource headroom is tested for **one German model in one Linux container**, not all nine languages together or production Render restart/idle requirements. The `max_requests=0` test setting is only safe as part of a defined external drain-and-restart policy plus much longer memory monitoring.
6. Public legacy `POST /translate` and `POST /translate-batch` remain outside the guarded controls in current production (experimental staging quarantine OFF by default). Nothing changed in production.
7. Only post-install Argos tree repeatability was verified; pre-install archive SHA, model licenses/publisher, patched-source security, dependencies and independent scientific translation QA remain unverified.
8. R123 gateway does not implement member identity/role checks, abuse quotas, CSRF/CORS policy, audit logging/retention/privacy governance or a trusted server-side broker. It is **not** a deployable authentication or data-privacy solution.
9. Source English remains canonical and all machine outputs are provisional/held; all nine FFH languages need qualified fluent review including safety critical weights/units, Arabic RTL, `fil→tl`, `zh-Hans→zh`, and protected-source approval gates.

## Next ticket R124 — crash recovery and readiness
Create a disposable, synthetic real-model crash-injection harness for the loopback gateway: kill the backend while a guarded request is *accepted* and while idle; verify the gateway returns sanitized 502 for uncertain accepted work, then bounded 503 for new work, transitions to 200 only after a demonstrably healthy new model worker, and never performs unsafe automatic retry. Add a lightweight backend watchdog/heartbeats and qualified Member-auth broker design; repeat resource/latency tests with prolonged load and faults. Keep a hard 512MiB cap and 15% reserve, no production writes, and always preserve evidence of failure.

**Current owner release decision: HOLD.** Never merge to Render auto-deployed `main` as a shortcut.
