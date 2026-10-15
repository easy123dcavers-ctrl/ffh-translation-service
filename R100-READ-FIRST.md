# FFH R100 two-account translation-engine benchmark — isolated tests only

## Scope and account plan
- Worker A: easy123dcavers-ctrl (this test branch), even IDs 0,2,...98 (50 invented English strings), English->Spanish.
- Worker B: KatsuraFukuryu (to configure separately), odd IDs 1,3,...99 (50 invented English strings). Clone this test script and use \`--shard-index 1 --target es\` for apples-to-apples throughput.
- IDs are disjoint; both test shards use the same 100 deterministic invented inputs.
- Collect the two \`summary.json\` and \`synthetic_drafts.jsonl\` files after both tests. Reconcile counts and unique IDs before claiming 100/100 measured.
- No parallel runs or data ingestion should be claimed until both account tests are actually confirmed complete.

## Hard safety gates
- This is TEST/DEVELOPMENT activity, not an ongoing GitHub Actions production translation factory. GitHub-hosted Actions may not be used for unrelated ongoing production compute.
- The 100 strings are entirely synthetic. Do not insert FFH production text, Supabase credentials, protected sources or real customer data into public repositories or test artifacts.
- No access to FFH Supabase, Netlify or Render from these test scripts; zero production writes and zero auto-approvals.
- Machine output is **provisional**, not approved. Flags check numerals and identical/empty text only; language accuracy and fermentation-safety terminology still need human QA.
- Public test artifacts expire in 3 days. Use no workflow secrets. Deploy Render only from main; this benchmark branch must not be merged/deployed as a runtime change.

## Worker B setup
Create a separate public **test-only** repo under KatsuraFukuryu (or grant the connected first GitHub account write access to a test-only repo). Add the same \`tests/r100_synthetic_shard.py\`. Copy the Worker A workflow and modify:
- workflow filename, name, and branch name for account B;
- \`--shard-index 0\` -> \`--shard-index 1\`;
- artifact name Worker A -> Worker B.
No FFH production files or secrets.

## What R100 can establish
- Measured translation-model runtime, peak process memory and per-item draft/hold counts for 50 invented samples per account.
- Whether splits return disjoint sample IDs.
- It does not establish production throughput or translation quality at scale and does not connect real FFH content.
