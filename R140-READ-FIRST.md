# FFH R140 — read first, isolated PostgreSQL verification

Date: October 17, 2026, Japan. **Experimental STAGING verification, not production rollout.**

## Verified milestone

GitHub Actions **38958626609** completed SUCCESS with **22/22 real PostgreSQL 16 integration tests**.
https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38958626609

- All tests ran in a disposable GitHub Actions service container (postgres:16, initialized as database `ffh_r140_ephemeral`).
- Driver pinned `psycopg[binary]==3.2.6`, Python 3.11.
- Real concurrent receipt insert uniqueness (16 connections), atomic quota reservations (16 connections), HMAC opaque receipts, cross-process crash tombstone, key epoch mismatch, no replay after UNKNOWN.
- Real database privilege tests: writer has access ONLY to the private ledger schema and scoped columns. Separate read role cannot access ledger. Writer cannot read fabricated unrelated public table, cannot delete receipts, cannot SELECT protected payload digest, cannot change the key registry.
- Actual committed receipt + simulated lost commit acknowledgment => admission 503 (deny) and subsequent replay 409 (never dispatch twice).
- Denied quota rolls back receipt and permits retry in a later DB quota window.
- Zero real member IDs, Supabase credentials or food-safety data in tests.

## Real issue discovered and resolved

First actual PostgreSQL run 38958223697: **18/20 pass, two fail closed**. The writer role had SELECT on `receipt_digest` but not on `state`. `UPDATE ... WHERE state='inflight'` checks `state`, so PostgreSQL required a narrow additional SELECT(state) grant. No broad table SELECT was granted. Second run 38958409003: **20/20 pass**. Third run 38958626609: **22/22 pass**.

## Strict boundary

R140 `r140/pg_real.py` is an isolated integration **port of the R139 receipt SQL contract**, not yet a direct wired production release of `r139/postgres_ledger.py`. R139 handoff archive remains the complete source of record for the broker and its 173 offline tests.
The CI database is disposable, with fabricated roles/passwords only. DO NOT reuse any synthetic secrets/credentials for staging or production. The dedicated roles, grants and row-security checks were exercised in CI, not installed in Supabase.

## Current release gates

1. Provision separately authorized real staging Supabase/Auth + PostgreSQL project, strong secrets, origin-pinned TLS, and independently reviewed least-privileged credentials. Not done.
2. Test the **actual R139 adapter and combined R138/R137 HTTP/Auth source gate** against real staging identities (revoked, banned, current terms, role changes); never impersonate auth.uid() or connect privileged keys in browser. Not done.
3. Integrate broker with backed-up receipt ledger (no persistent local SQLite), negative auth and abuse limits, fail-closed session changes and science/language QA.
4. Preserve English original, safety-review holds, provisional translations only; no automatic Reviewed or publishing.
5. Run Android, browser and Netlify/Render staging parity tests; independent release security review.
6. GitHub `main` remains untouched: Render may auto-deploy from main. No Netlify deployment, Render changes, or production Supabase writes.

## Continuation instructions

- Prefer followup R141 staging Auth test ONLY with a separately authorized staging database/project. R140 CI is reproducible with a branch-only workflow and does not need a new staging account to be created.
- Reuse the 22 real PG tests; add exact R139 adapter parity tests and zero-privilege verification.
- Keep the owner's approved 10% headroom minimum under 512MiB/0.1 CPU; R135 full real nine-language resource test passed 1823.01 seconds, 45.01% spare, 1525 synthetic items and 0 OOM (run 38948743697). This remains resource-only.
- Return ONE cumulative MC handoff ZIP including the prior R139 ZIP, code, exact GitHub refs and failing/pass evidence. The user uploads Netlify artifacts, but this is NOT a deployable site ZIP.
