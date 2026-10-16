# FFH R124 — Remaining Work Tracker (translation service only)
Date: 2026-10-16. This tracker separates ENGINE PERFORMANCE from content completion.

## New 20% RAM headroom policy
- Hard limit: 512 MiB; max permissible observed cgroup peak: 409.6 MiB; any OOM kill = FAIL. Exact unrounded integer-byte check, not a rounded percentage.
- German `en→de` is VERIFIED for the strict gate, with `ARGOS_BATCH_SIZE=1`, `ARGOS_BEAM_SIZE=2`; **two independent full gateway restart-soak tests PASSED** (peak 283.85 and 281.06 MiB; 44.56% and 45.10% headroom).
- German batch1/beam4 failed twice at 512MiB despite an earlier isolated pass. Do not promote from a single earlier success.
- Eight remaining model mappings to re-test independently under the strict standard: `en→es`, `en→fr`, `en→ja`, `en→ar`, `en→tl`, `en→ko`, `en→vi`, `en→zh`. **Resource success for `tl` does not certify FFH `fil`; generic `zh` does not certify Chinese Simplified script.**
- R124 real GitHub Jobs [matrix](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38864857101) and [Spanish separately](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38865037536) are the source of truth. Individual model job failure, 503 error, timeout or OOM must never be counted as pass.
- The first eight-target dry run [38864512811](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38864512811) was invalid for technical qualification: inherited test runner restricted target language to `de/ko`, and `es` lacked a stored model byte-tree baseline. Corrected R124 runner and test Dockerfile for all languages. Spanish installed model tree first observed in [38864824281](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38864824281), bytes=96243365 SHA256=b2c84f20889ba883ce7b2b29fe264017731a3e9e134410348453163148c2fca1. This is **post-install repeatability only, NOT verified publisher/archive provenance or license**.
- The R124 tests keep one Argos model per 512MiB Docker container, 1 CPU, runtime offline, real Flask/Gunicorn guarded endpoint, loopback test gateway, no cached member data, 4 controlled master lifecycles, 3 intentional restart gaps returning 503, strict 429 admission, held/no-draft contract, no automatic approvals.

## Distinct release workstreams still OPEN (no made-up overall percentage)
1. **Memory and cold-start reliability for all nine models:** pass at least 20% headroom *repeatedly*, long text, batch/load, health and restart; do not infer from other languages.
2. **Crash and uptime reliability:** 30+ min and production-shaped stress; unexpected SIGKILL/worker death and idempotency/unknown-outcome behavior. R123 demonstrates controlled planned restarts only.
3. **Secure FFH Member/Owner authorization:** audited trusted server-side broker and session/JWT validation, quotas and abuse safeguards. The current staging bearer is NOT FFH member authentication and must never be shipped in public Netlify JS.
4. **Remove legacy bypass and complete client migration:** `/translate` and `/translate-batch` current production contract is not protected by staging flags; safe 401/429/503 behavior, permissions, mobile UX and rollback needed.
5. **Supply chain and privacy:** authenticated archive hash BEFORE model unpack/install, verified package/model licenses, independent source patch/dependency security review, logs/retention/secrets controls.
6. **Quality, science and translation governance:** nine independent fluent-language + fermentation safety reviews (temperatures, salinity, acidity, protected source strings); preserve canonical English and safe translation-memory approval workflow. Every model result remains provisional or held.
7. **Owner-authorized launch and rollback:** integration across FFH staging, Render/Netlify/Supabase only after gates. Minimize Netlify credit deployments and never merge test branches to Render-auto-deployed main.

## Counts definition
Passing one language's resource suite advances the **20%-headroom test coverage counter**, not the count of published translations or overall site completion. The full nine-language translation backlog is maintained separately in Supabase; this R124 test does not query or change production counts.

**Current production remains HOLD and unchanged.**
