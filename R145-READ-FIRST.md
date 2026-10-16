# R145 READ FIRST — Final receipt state consistency (2026-10-17)

**Verified:** GitHub Actions run https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38971589789, CI-tested SHA `fbb211a40c304edc1bc7143c48e5b203af81da79`, success **75/75 tests** (45 real PostgreSQL 16 original receipt/quotas/permissions, 15 genuine GoTrue Auth and post-inference safety checks, 15 new receipt fault/concurrency tests). Production `main` still `5f8bcecba92653f653ef4514c6fcf32d9d6efbe9` on final pre-packaging check.

## Important fix

The R144 core marked a request `done` before the last safety and Member authorization checks, so a withheld draft incorrectly retained a `done` receipt. In R145 `r144/guarded_completion.py` a per-request `_DeferredReceiptLedger` defers the core's `done` write until after both final checks succeed, and also binds final Member user-ID to the initially admitted identity. On late denial the status commits `held`; on failed/uncertain database commit it refuses response with 503; crashes leave permanent non-replayable `inflight`. R139 atomic quota and original broker SQL remain unchanged. R144 real GoTrue tests assert `held` rather than `done` for revoked sessions, suspended members and revoked terms. R145 15 additional tests cover late source changes, exception paths, no-replay, concurrency and uncertain commits.

**Precise semantics:** `done` means that final validation allowed the server to return a provisional response; it is NOT confirmation that the browser received HTTP content. `held` means content was withheld. Never automatically replay an `inflight`, `unknown`, `done` or `held` nonce.

## Release HOLD

All work is on isolated GitHub branch. CI uses disposable local Auth+Postgres with fabricated accounts. **No live hosted FFH staging authentication, real Member data, science/translation approval, or Netlify/Render mobile integration was tested.** Do not merge `main` or deploy, copy credentials, approve machine translations or write production Supabase. The private Auth SECURITY DEFINER helper requires independent review and hosted staging schema parity. Keep safety/quality approvals separate, R135 512MiB 0.1CPU with >=10% headroom, and Member Android regression. Existing hosted `FFH-Language-Safety-Staging` is not yet schema matched.

Full MC handoff file: `FFH_R145_FINAL_RECEIPT_CONSISTENCY_VERIFIED_HANDOFF_2026-10-17.zip` provided in ChatGPT, containing exact tested source and logs, SHA256SUMS, R144 complete nested predecessor and zero-retraining instructions.
