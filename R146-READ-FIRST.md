# FFH R146 — HOSTED STAGING READ FIRST (2026-10-17 JST)

**Outcome:** Hosted safety-staging isolation verified; **13/13 live HTTPS/negative Auth/public-REST security probes PASS**, GitHub Actions run [38973583732](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38973583732). **No real Member positive login test yet**. R145's real GoTrue/Auth+PostgreSQL positive tests **75/75 PASS in isolated CI**, preserved in previous handoff. Do not confuse synthetic GoTrue with existing hosted Supabase.

## Projects and changes
- Production Supabase project: `kowdicvwscnbwautczya`. READ ONLY schema checks, ZERO writes.
- Existing separate `FFH-Language-Safety-Staging` project: `hlsjzjnondimwhqbgjqm`. 0 Auth users before R146 and no `public` tables. Production is unrelated.
- Applied exactly THREE migrations, all within the existing staging project, never production:
  1. `ffh_r146_sandbox_namespace_only_20261017` (creates strictly private schema, revokes PUBLIC/anon/authenticated usage).
  2. `ffh_r146_private_member_and_safe_source_fixtures_20261017` (seven private RLS + FORCE RLS tables, one current synthetic terms version).
  3. `ffh_r146_private_nonlogin_reader_and_denied_public_rpcs_20261017` (NOLOGIN restricted reader role and two private narrowly scoped functions).
- One fabricated English source and normal test gate written to sandbox ONLY: `FFH R146 interface label for staging verification.` The hash is SHA256 of UTF-8. NOT a real FFH registry row, NOT human-approved content and never to publish.
- One temporary protected-source override was inserted; the private source function returned false as required; the override was DELETED. Current staging has 1 mock source, 1 mock review, 0 protected overrides, 0 member profiles, 0 terms acceptances, 0 staff roles, 0 new Auth accounts, 0 live receipts. No production translation or Auth data copied. The existing separate `ffh_safety_test` schema was untouched.

## Verified external permissions (hosted)
- `ffh_r146_sandbox` schema usage: anon=false; authenticated=false; custom NOLOGIN reader=true.
- `ffh_r146_sandbox.member_status(uuid,uuid)`: anon EXECUTE=false; authenticated EXECUTE=false; NOLOGIN reader=true.
- `ffh_r146_sandbox.safe_source(text)`: anon EXECUTE=false; authenticated EXECUTE=false; NOLOGIN reader=true.
- Source function: registered synthetic ordinary=true; unregistered=false; empty=false; temporarily protected override=false.
- Member function: fabricated nonexisting UUID/session returns zero rows; no synthetic Auth user was forged.
- Live GitHub R146 test [38973583732](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38973583732): 13/13 PASS; TLS health 200, Auth settings 200, invalid/malformed/unsigned tokens refused; private schema and private RPCs returned HTTP 406 when explicitly selected; public FFH Member/source tables still not exposed.
- Public project publishable key in isolated GitHub workflow is intended for frontend use (NOT a service/secret key). No database passwords or private JWT keys in test code.
- GitHub main SHA from end-of-run verification: `5f8bcecba92653f653ef4514c6fcf32d9d6efbe9`; NEVER merge without release approval (Render may auto-deploy).

## Security hold uncovered in EXISTING staging (not R146)
Supabase security advisor flagged existing `public.ffh_translation_learning_register_html_fragments(text,text,text)` as SECURITY DEFINER EXECUTE-capable by both anon/authenticated. It references the absent helper functions `ffh_translation_learning_register_text` and `ffh_translation_learning_is_safety_text` in current staging (read-only dependency survey). It was NOT created by R146. Do NOT exercise with untrusted inputs or change without reviewing related staging safety tests. Recommended to assess REVOKE EXECUTE from anon/authenticated after impact review.
Docs: https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable
Advisor INFO "RLS enabled no policy" for the seven R146 tables is INTENTIONAL DENY ALL. Do not create public RLS policies to silence this informational lint.

## Remaining gates — no fictional readiness
1. Real hosted test account with genuine verified email login and a current Auth session under this existing staging project. Do NOT insert an artificial `auth.uid()` / fake session or manually copy real members. Auth settings show email signup enabled, but confirmation/test-account arrangements are not authorized/provisioned.
2. Independently reviewed TLS/privileged server-only credential for the NOLOGIN reader design; no browser access to any privileged key. The current role is NOLOGIN by design; cannot connect to hosted PG yet.
3. Provision a separate restricted writer and R139 durable receipt/quota tables in hosted staging, with backup, key epoch, revocation, retention and secret management approved; **not installed in R146**.
4. Connect full R145 guarded broker to hosted staging Auth identity & safety source gates; run staged positive tests, then Android/Netlify/Render parity and safety/language QA. Do not publish automatic translations.
5. Do not tamper with existing `ffh_safety_test` staging tables; use isolated schema.

**Artifacts:** full R146 ZIP provided to user nests previous R145 handoff + exact 13-test GitHub evidence; SHA256SUMS and standalone verification. No Netlify/Render deployment. Owner retains deploy control.
