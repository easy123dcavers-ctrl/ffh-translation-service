# FFH R148 — READ FIRST (staging durable admission, 2026-10-17)

## Verified
- **R147** real Android magic-link login, Member status, current staging terms and canonical synthetic English source/PATTERN: screenshot showed PASS. No JWT was shared.
- **R148** backend installed in **existing separate** `FFH-Language-Safety-Staging` project `hlsjzjnondimwhqbgjqm` only; production project `kowdicvwscnbwautczya` untouched.
- Private tables: `ffh_r146_sandbox.r148_hmac_key` (one newly generated random 32-byte server key), `r148_receipts`, `r148_quotas`. Forced RLS; anon/authenticated have zero direct table privileges; public schema does not expose private tables.
- One authenticated RPC `public.ffh_r148_stage_admit(p_source,p_target,p_nonce)` checks live `auth.uid()`, signed JWT session_id, real session status, test Member profile, current terms, approved synthetic source, target and bounded nonce. No spoofed auth.uid was used. It creates only a HMAC-keyed **HELD** receipt and atomically reserves up to **3 per user per 60-second bucket**; duplicate nonce denied. If quota rejects, the receipt is rolled back. No plaintext source, JWT, user UUID or draft is stored in the receipt/quota tables.
- Preflight DB queries: anon EXECUTE false, authenticated EXECUTE true, no auth returns denied, no authenticated direct private-schema access, no credential read access, one random key installed; zero test receipts/quotas at latest read. **Positive held-request and concurrent quota behavior still require a real signed in-browser or dedicated controlled test; only static/negative automated checks passed.**
- GitHub Actions [R148 verified run 38982233254](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38982233254) **26/26 PASS**, comprising 10 R147 regression and 16 R148 static/real negative hosted HTTPS checks. **Do not misstate this as a full nine-language translation test.**
- The tested `docs/index.html` and `docs/r148.js` from this R148 branch were copied byte-for-byte to existing **R147 GitHub Pages source branch** `ffh-r147-hosted-member-auth-probe-20261017`. No further Pages settings needed. Public Pages address: https://easy123dcavers-ctrl.github.io/ffh-translation-service/. This is not FFH production or Netlify.
- Production GitHub main sha from pre-packaging check: `5f8bcecba92653f653ef4514c6fcf32d9d6efbe9`; never merge to main without review because Render may auto-deploy.

## Owner's next Android test
1. Open the existing public staging Pages link above in Android Chrome; if an old page remains, refresh. New page contains a staging request test and duplicate test button, but both stay disabled until a real Member login passes again. **Do not share tokens or magic links**.
2. If asked for email, use the existing staging account's email and request a fresh sign-in link. Follow email to return to Pages. The ordinary Member check should PASS.
3. Tap **Test secure staging request (no translation)** once. Expected: "PASS: one durable staging request recorded as HELD." No text is sent to Render.
4. Tap **Test duplicate protection**. Expected: same request rejected as duplicate. A new fresh ID is generated on each page load. Screenshot only the status text, hide browser tokens.
5. Coordinator verifies receipt count + quota count with read-only Supabase SQL (no HMAC secrets read or printed). If any failure, fail closed and repair on branch; do not imply server/translator readiness.

## Strict remaining holds
- R148 HMAC test ledger is **independent from R139/R145 broker key epoch**; do not intermingle keys, copy secrets, or claim R145 distributed ledger is deployed. R145 Python broker with atomic admission, final late-session/source check and proper 'done'/'held' states is NOT yet connected to live hosted staging; no server-only restricted Postgres credentials or model-only transport have been commissioned.
- `model_connected=false` on all R148 responses; all receipts start `held`. **No machine translation, publication, ingestion, or review occurred**. The interface shows no draft.
- SQL function is a narrowly gated SECURITY DEFINER in exposed `public`. Supabase advisor flags authenticated-executable definer functions R147/R148; independent review before any release. Prior unrelated old staging anonymous-executable SECURITY DEFINER remains unresolved. Intentional RLS no-policy INFO indicates private deny-all tables; do not add public policies to silence.
- Future: genuine hosted positive test, concurrency and quota test, per-session anti-abuse, independent privileged SQL review, TLS server credentials, R145 backend + R135 model integration with 512MiB/0.1CPU >=10% headroom, nine-language quality and science holds, full Android QA. No production writes/deploys.
- Previous handoff: nested ZIP includes R147→R146→R145 etc. Return ONE cumulative handoff ZIP.
