# FFH R112 — Nine-language Argos package availability inventory
Date: 2026-10-16. Research only; no production changes.

## Source / reproducibility
Read-only inspection of Argos Translate's published package index from an immutable upstream Git commit:
- https://raw.githubusercontent.com/argosopentech/argospm-index/ff90de60728f7c1338ff6b75974e4c89b2442d22/index.json
- Raw main ref at time checked: `ff90de60728f7c1338ff6b75974e4c89b2442d22`
- Index includes 100 package entries, 49 listed with `from_code=en`; **all nine FFH target mappings had one direct model entry at that exact index revision**.
- Exact data is recorded in `reports/r112-argos-nine-language-package-index.csv`.

| FFH target | Argos target | Model version | Direct English model listed |
|---|---|---:|---|
| es | es | 1.0 | Yes |
| fr | fr | 1.9 | Yes |
| ja | ja | 1.1 | Yes |
| de | de | 1.3 | Yes |
| ar | ar | 1.0 | Yes |
| fil | tl | 1.9 | Yes |
| ko | ko | 1.1 | Yes |
| vi | vi | 1.9 | Yes |
| zh-Hans | zh | 1.9 | Yes |

## Important restrictions
"Listed" means an entry appears in the public Argos package index; this **does not mean** each package was downloaded, checksum-pinned, loaded into the lightweight 512 MiB service, quality checked, free of licensing issues, or deployed. The R109–R111 memory tests have validated ONLY the English→Spanish model. There may be large differences in model sizes, CPU behavior, latency, and language accuracy.

The FFH site language tag `fil` maps here to Argos `tl` Tagalog. This does not certify correct regional Filipino spelling, wording or register. FFH `zh-Hans` maps here to generic Argos `zh` Chinese; **Simplified-vs-Traditional script is not verified** by the model listing. Arabic requires additional RTL rendering and punctuation tests. Avoid direct equality assumptions for `fil`/`tl` or `zh-Hans`/`zh` in database approval flows.

No Argos model output is reviewed or automatically approved; all generated text is provisional and high-risk fermentation/safety content is held behind existing FFH human approval gates. Never ingest safety-protected sources, bypass RLS, change Render/Netlify, or merge experimental branches to production.

## Next work ticket
Develop a lightweight, isolated single-target matrix to load each of the nine Argos models individually under true 512 MiB cgroup. Test warm/cold memory, a small multi-sentence sample, numerical/placeholder preservation, long-term responsiveness, crash/restart and language-specific presentation. Record model URLs/checksums and license provenance. Do **not** attempt to load all nine Argos models into one free 512 MiB process. Independent fluent-person linguistic and fermentation safety QA is mandatory before production release.

## Verified companion
R111: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38837736796 — English→Spanish, 100 successful batch items + 6 longer requests, two Gunicorn startups, memory peak 219.39 MiB with 57.15% headroom, 0 OOM.
