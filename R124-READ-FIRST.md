# FFH R124 — NINE TARGET LANGUAGES PASS HARD 20% MEMORY GATE — READ FIRST
Date: 2026-10-16. Isolated engineering only. **PRODUCTION RELEASE REMAINS HOLD.**

## Measured accomplishment
All NINE FFH target-language mappings now have **at least one real-model, isolated, full four-lifecycle test** with at least 20% spare RAM, 0 OOM kills, no automatic approval and enforced 512 MiB Docker cgroup/1 CPU. This is **100% of the initial new memory qualification**, NOT 100% of translations, publication readiness, or the project.

German (en→de) previously passed **twice** on branch `ffh-r123h-headroom20-20261016`, Argos batch1/beam2, peaks 283.85 MiB (44.56%) and 281.06 MiB (45.10%), after beam4 failed twice at 512 MiB. New R124 isolated work requalified eight other language mappings:
| FFH target | Argos target | Inference batch / beam | Peak 512MiB cgroup RAM (MiB) | Remaining RAM % | Batch-item occurrences | Result |
|---|---|---|---:|---:|---:|---|
| Arabic | ar | 8 / 4 | 221.07 | 56.82% | 450 | PASS |
| Spanish | es | 1 / 4 | 220.96 | 56.84% | 425 | PASS |
| French | fr | 8 / 4 | 222.23 | 56.60% | 975 | PASS |
| Japanese | ja | 8 / 4 | 262.74 | 48.68% | 1,025 | PASS |
| Korean | ko | 1 / 4 | 257.90 | 49.63% | 375 | PASS |
| Filipino/Tagalog | tl | 1 / 4 | 218.99 | 57.23% | 825 | PASS* |
| Vietnamese | vi | 8 / 4 | 205.50 | 59.86% | 400 | PASS |
| Simplified Chinese/general Chinese model | zh | 8 / 4 | 215.53 | 57.90% | 450 | PASS* |

*Pass is only the **resource/HTTP model**: `fil→tl` language mapping and `zh-Hans→zh` Simplified Chinese regional/script fidelity are NOT reviewed/certified.

Combined R124 eight target models: **4,925 invented batch item occurrences** across distinct independent containers, **417 held/no-draft results**, **4,508 provisional results**, ZERO approved translations, ZERO production writes, ZERO OOM kills, and ZERO reported gateway transport errors. Every run completed four Gunicorn master lifecycles with three controlled planned restarts, guarded 429 overload protection, explicit 503 during planned gaps, legacy 410 quarantine, test-only bearer 401 rejection, no runtime network, and at least 20% peak headroom. Do not add batch-item occurrence totals to production translation-memory row counts.

## GitHub run evidence
- German two-pass hard 20% evidence: [German profile sweep](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38863208567) and [German independent repeat](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38863598097). Sweep workflow conclusion FAILED because deliberately included beam4=512MiB OOM HOLD; the beam2 and beam1 matrix jobs passed. Do not declare the entire sweep successful.
- Seven-model R124 matrix: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38864857101 — **7/7 SUCCESS**.
- Spanish fresh observed baseline, no release trust: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38864824281 — SUCCESS, first installed EN→ES model tree bytes=96243365, SHA256=b2c84f20889ba883ce7b2b29fe264017731a3e9e134410348453163148c2fca1.
- Spanish second independent model reinstall, observed tree equality enforced, full 20% RAM gateway test: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38865037536 — SUCCESS. Still **not** publisher/authenticated archive provenance.
- Initial eight-target R124 trial: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38864512811 — FAILED due to **inherited test-runner allowlist only de/ko** and ES absent stored checksum; code/test orchestration problems, NOT model resource failures. Corrected by R124 all-nine-target runner and separate ES check. The handoff retains this finding; never hide it.

## Code and tight acceptance rules
- Test branch: `ffh-r124-eight-language-20pct-20261016`, derived from previously isolated `ffh-r123h-headroom20-20261016`. NO merge to auto-deployed main.
- `tests/r124_eight_language_gateway.py`: R123 gateway real-model 120s/four-lifecycle test with corrected allowlist for nine Argos model target codes and exact `memory_gate` function.
- `tests/r124.Dockerfile`: copied all-nine-target checker into isolated image, preserves 1-model build plus pinned lightweight Argos and pre-installed English MiniSBD model.
- `.github/workflows/ffh-r124-eight-language-20pct.yml`: seven initial still-model-pinned language profiles, 512MiB cgroup, max four concurrent CI jobs, individual artifact retention.
- `.github/workflows/ffh-r124-es-baseline.yml` + `tests/r124_es_observe.Dockerfile`: first ES installed-tree bytes/SHA observation, without misleading release certification.
- `.github/workflows/ffh-r124-es-pinned-20pct.yml`: independent ES reinstall+tree equality plus full gateway test.
- `models/r119_observed_model_trees.json` on this TEST branch includes observed ES tree hash alongside R113 eight older languages. Hashing AFTER download/install demonstrates repeatability only; must audit model source/license and exact archive checksum BEFORE installation for a real release.
- `tests/r123h_memory_policy.py`: strict exact bytes `memory_peak*5 <= 512MiB*4` and OOM=0; permitted peak <=409.6 MiB. Guarded stage API and client do not expose any Member text or real token.

## Seven major workstreams remaining (not mathematical project %)
1. **Longer and repeated reliability**: 30+ minute and unexpected SIGKILL/worker crash tests, cold starts, high load/long text, one-instance pressure, retry/unknown-result responses. The nine new tests were one short (~2min) real-model pass per target (except German two passes). Run second round for other eight before certifying repeated memory reliability.
2. **Trusted real FFH Member-authenticated server-side broker**: authenticate session/JWT, quotas, roles, request limits. Never ship the synthetic shared stage bearer in public Netlify JavaScript.
3. **Retire/broker legacy endpoints**: production `/translate` and `/translate-batch` remain unguarded by experimental staging flags; client migration and actual abuse controls required.
4. **Model/software supply-chain and privacy**: verify publisher archive SHA before unpack/install; independent model-license compliance, modified Argos source/dependencies vulnerability review, request-log secrecy/retention, secret management.
5. **Language correctness**: independent fluent + fermentation scientific QA for ALL nine languages, numeric/salinity/acidity/temp/units/food safety, `fil→tl`, `zh-Hans→zh`, Arabic RTL presentation. Passing a resource gate does not imply proper translations.
6. **Translation memory / governance integration**: reviewed-state immutability and protected-source approval; no model output self-approves or writes to production. Translation row backlog is separate from language model count and not measured in these tests.
7. **Owner-controlled staging/rollout/rollback**: true Render/Netlify/Supabase end-to-end dummy-member flow, security QA, privacy controls, rollback and low-credit Netlify release schedule. Never merge experimental branches directly to production as a test.

**Production Render, Netlify, and Supabase remain UNCHANGED. No automatic safety-source publication. Release HOLD.**
