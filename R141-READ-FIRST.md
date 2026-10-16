# FFH R141 — VERIFIED 45/45 REAL POSTGRES / EXACT ORIGINAL R139 SOURCE
**2026-10-17, Japan | zero-retraining Main Coordinator checkpoint | experimental only**

## Completed VERIFIED

- R141 GitHub run **38964131415** SUCCESS: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38964131415
- CI PostgreSQL service image **postgres:16** + Python 3.11 + pinned psycopg[binary]==3.2.6.
- Combined tests: **45/45 PASS** (R140 22 reference PG + **R141 23 original R139 broker ledger** real PG).
- All new parity tests use the byte-identical original `r139/postgres_ledger.py`, `r139/identity_hash.py`, and `r136/broker.py` from R139 handoff. Verified Git blob SHA1:
  - `r139/postgres_ledger.py`: 206b662d9157d7b0334ddf45179f9ca5b5a034e6
  - `r139/identity_hash.py`: 6d034a807e93ac42145f3b2c0759a90696bc871b
  - `r136/broker.py`: d6cd7540b2c4f5f4877198950920c050cd577fdb
- Local rerun of unmodified R139 ZIP **173/173 offline tests PASS** (without live external accounts).
- R141 real PG behavioral coverage: duplicate single-winner 16 connections, quota atomic 16 connections, no receipt after quota rejection, permanent tombstones for UNKNOWN/done/held, actual killed child process, lost COMMIT acknowledgment after actual DB commit, key epoch rotation refusal, synthetic Member denial, canonical safety deny, provisional-only output, backend crash with no replay, least-privilege writer cannot delete/select protected payload.
- R140 role fix PRESERVED: SELECT on only receipt_digest, state; no extra table SELECT. No direct FFH production data accessed.

## New discovery: nonproduction stage exists but **wrong schema**
Supabase read-only project inventory showed existing `FFH-Language-Safety-Staging` project `hlsjzjnondimwhqbgjqm` (read-only SELECT metadata only).
Missing there on October 17: `ffh_staff_roles`, `ffh_member_profiles`, `ffh_terms_acceptances`, `ffh_translation_memory`, `ffh_translation_accuracy_review`, `ffh_translation_protected_source_overrides`, and `ffh_broker_private` tables.
DO NOT mistake staging project existence for authentic Member permission parity. No staging or production database writes done. A separately approved staging schema/data approach is necessary.

## Still HOLD for live production
- Real staging Supabase Auth accounts, terms/version and authorization corpus missing. No end-to-end auth proof.
- Full original R139/R138 HTTP broker including live token verification and source gate not yet exercised against real staging Auth or full staging database.
- Durable secret provisioning, TLS verification, proper database endpoint/revocation/account lifecycle, rate limits, backup and retention review.
- Provisional ML translation content must never become Reviewed/published automatically; separate fermentation science and language approval.
- Browser/Android regression, staged Netlify/Render deployment, baseline website integrity and release rollback.

## Resource milestone stays verified
R135 real nine-language **1823.01s (30m23s)**, **1525** synthetic items, 3 language circuits, **281.55MiB peak / 45.01% headroom**, zero OOM, 512 MiB / 0.1 CPU. Run 38948743697. Resource-only.

## Next action
1. Keep R141 branch isolated; do not merge to `main` (Render auto-deploy).
2. Prepare **schema-matched staging** with explicit cost/security review; no copying real Member PII/auth secrets. Validate actual FFH role and source eligibility semantics.
3. Build R142 real staging identity tests only after obtaining explicit authorization and proper credentials; use synthetic test accounts owned by FFH.
4. Use previous R139 and R140 ZIPs as complete source packages; R141 CI branch is the authoritative test source. Report exact run, SHA and acceptance criteria.
5. One ZIP per milestone, Android-friendly user instructions, frequent TICKER with verified percentages.
