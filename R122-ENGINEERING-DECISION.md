# FFH R122 — Gunicorn connection reset investigation (engineering evidence)
Date: 2026-10-16. **Test branches only. Production unchanged.**

## Proven failure boundary
R121d German, real Argos EN→DE model with `ARGOS_BATCH_SIZE=1`, 512MiB Docker cap and 1 CPU:
- Gunicorn `gthread` worker auto-recycle `--max-requests=12` failed after 50 batch items; `max-requests=24` failed after 150 items with **ConnectionResetError**, while memory remained ~280MiB.
- `max-requests=48` completed 450 items in a two-minute run with healthy memory and admission; **it did not actually trigger auto-recycling and the CI correctly failed the recycling proof requirement**.
- R122 controlled transport A/B test: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38858513619 — **both** forced `Connection: close` plus Gunicorn `--keep-alive 0` and default keep-alive settings FAILED at `max-requests=24`, after 150 items, with TCP connection reset (not OOM). Memory peaks ~282.71MiB and ~281.89MiB respectively. This rejects the hypothesis that HTTP keep-alive reuse alone caused the resets.

The installed Gunicorn 23.0.0 `gthread` implementation in public upstream source, at `handle_request()`, sets `self.alive=False` once `self.nr>=self.max_requests`, logs `Autorestarting worker after current request`, and forces the current response's connection closed. Source: https://raw.githubusercontent.com/benoitc/gunicorn/23.0.0/gunicorn/workers/gthread.py. It is plausible that simultaneous/newly accepted TCP connections can be dropped during this transition; **this is a mechanism consistent with the logs, not a complete root-cause proof or a confirmed Gunicorn upstream bug**.

## R122b alternative under test
Branch `ffh-r122b-quiescent-restart-20261016` disables automatic per-request worker recycle (`max-requests=0`) in its disposable test container and tests **four serial Gunicorn master lifecycles** over ~2 minutes.
- 1 Gunicorn worker, 2 threads, no runtime internet, real pinned test model, 512MiB cap, 1 CPU, Argos batch1 beam4.
- In each lifecycle, run guarded 25-item batches with simultaneous HTTP 429 load, strict auth, legacy 410 quarantine, health under load, held/provisional safety checks.
- At each planned restart, **wait until all accepted requests finish** and prove the cross-process admission `flock` is free. Then stop the master and start a new master. Verify four distinct master PIDs and exactly one worker boot per master (no automatic worker recycling).
- No client is issued a translation request during the deliberate offline gap between masters. This is **not** proof of zero-downtime service operation; a trusted broker must refuse/queue requests before draining and provide explicit safe retry semantics.
- The CI result is NOT assumed in advance: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38858738514.

## Mandatory acceptance / release design
1. Preserve hard 512MiB cap, at least 15% memory headroom, zero OOM kills, healthy `/health` responses while serving guarded requests, 25-item maximum, zero automatic human approvals, no Supabase writes.
2. Strong service readiness/draining handshake from a trusted backend broker, with authenticated member-scoped admission and bounded 429/503 semantics and no blind replay of text when a request's completion is unknown.
3. Never allow public legacy `POST /translate` or `POST /translate-batch` bypass; staging quarantine is OFF by default and production is not migrated.
4. A service can return a planned `503 Retry-After` **before** accepting work, but after an accepted request's TCP connection breaks the client cannot assume whether it finished. Use explicit idempotency and durable operation tracking if retrying server actions; provisional translation-only response has different semantics but should still not silently duplicate charge or submit protected content.
5. A one-instance, one-host `flock` does NOT coordinate multiple replicas or a broker. Under a 512MiB plan, overlapping warm model processes may OOM. Do not attempt zero-downtime two-process model overlap without independent cap validation.
6. A two-minute profile is not a long-term memory bound. Before release, repeat with 30+ minute real-shaped synthetic workloads and crash/timeouts, cold starts, browser/mobile and privacy.
7. Model-archive SHA before installation, model license/supply-chain, independent source patch security review, FFH identity broker and all nine languages' native/fluent fermentation-safety QA remain outstanding.

**Owner release decision: HOLD.** None of the R122 work was merged to auto-deployed `main`, deployed to Render/Netlify, or written to Supabase. Nothing was approved or published.
