# FFH R113 — EIGHT-LANGUAGE MODEL MATRIX — READ FIRST
Date: 2026-10-16. GitHub Actions isolated tests ONLY. No Render or Netlify deploys, no Supabase reads/writes or approvals.

## Verified evidence
Two GitHub accounts, identical seven source/test files checked by matching Git blob SHA, each using a separate branch and two-at-a-time 512 MiB Docker test matrix.

- Worker A successful run (fr, ja, de, ar): https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38838979965
- Worker B final run (ko, vi, zh succeeded; tl FAILED MEMORY HEADROOM): https://github.com/KatsuraFukuryu/ffh-translation-tests/actions/runs/38838983992
- Earlier A/B runs failed before model translation due to test-harness ARGOS_PACKAGES_DIR mismatch; checker path was corrected, with provenance in commit histories.
- 10 invented batch inputs plus one 664-character multi-paragraph input per language, Flask/Gunicorn one worker/two threads, network disabled at runtime, Argos 1.11.0+ffhlite1, cache OFF, one direct model installed, no OOM kills and concurrent /health successful.
- Human approval count remains ZERO. Passing tests do not establish linguistic quality.

## Resource results — strict minimum 15% headroom
| FFH locale | Argos target | model version | peak 512MiB cgroup MiB | headroom | CI job |
|---|---|---|---:|---:|---|
| fr | fr | 1.9 | 211.88 | 58.62% | PASS |
| ja | ja | 1.1 | 258.98 | 49.42% | PASS |
| de | de | 1.3 | 283.16 | 44.70% | PASS |
| ar | ar | 1.0 | 221.43 | 56.75% | PASS |
| ko | ko | 1.1 | 262.05 | 48.82% | PASS |
| vi | vi | 1.9 | 205.40 | 59.88% | PASS |
| zh-Hans | zh | 1.9 | 255.51 | 50.10% | PASS for **generic zh model** ONLY |
| fil | tl | 1.9 | 443.23 | 13.43% | **FAIL** strict 15% memory headroom |

## Integrity/review holds
- **All 8** models failed literal placeholder preservation on the one `{{SAMPLE_ID}}` invented fixture: **never feed unprotected interpolated text into Argos for FFH publishing or approval**.
- `ar` and `zh` also triggered literal numeric mismatch on 1 batch fixture each. Localized numeral scripts or formatting may explain some changes; review meaning, not just literal characters. For safety content ANY unreviewed numeric/unit change is a HOLD.
- Total flagged output occurrences: FR 1, JA 1, DE 1, AR 2, KO 1, VI 1, ZH 2, TL 1 = 10/80 tested batch occurrences flagged mechanically. Not independent linguistic assessment; candidates remain provisional.
- FFH `fil` → Argos `tl` is an approximation, not certified Filipino locale quality.
- FFH `zh-Hans` → Argos `zh` has NOT been checked for Simplified Chinese script. Needs fluent review. Arabic needs RTL QA.

## Explicit ambiguity to prevent misreporting
The `tl` test artifact's `summary.json` has internal `status=PASS_RESOURCE_API_PROVISIONAL_ONLY` because that field was assigned BEFORE the final 15% headroom assertion. **The authoritative GitHub CI job is FAILED, and the true R113 decision for Tagalog is HOLD/FAIL for inadequate memory margin.** Follow-up should fix this reporting-order bug before reuse, with offline regression tests. Do not hide, downgrade or omit this failure.

## Reproduce
A branch `ffh-r113-model-matrix-a-20261016`; B branch `ffh-r113-model-matrix-b-20261016`.
Script `tests/r113_single_model_matrix.py`, container `tests/r113.Dockerfile`, workflow `.github/workflows/ffh-r113-matrix-a.yml` or `ffh-r113-matrix-b.yml`.
Each job uploads a synthetic-only ZIP under `ffh-r113-{a|b}-{target}` (3-day retention) including `summary.json` with model manifest SHA256 and up to five largest model files and their hashes. Save these evidence files in permanent MC handoff.
The model download is not yet SHA-pinned *before installation*, which remains a release blocker. Artifact hashes prove what was installed on test runners, not chain-of-trust or independent source integrity.

## Next guarded engineering tasks
1. **R114:** exact placeholder/URL/units preservation and fail-closed validation, offline regression QA; do not silently rewrite or approve compromised text.
2. **R115:** Tagalog memory optimization or separate hosting strategy, with 15%+ headroom in a hard 512MiB cap, AND Filipino language review.
3. Independent native linguistic + fermentation scientific safety QA for all 9 FFH languages. No mass ingestion, no safety bypass, no publish.
4. Pin/verify models, dependency supply chain, language-script correctness, confidentiality, request-size and rate controls.
5. Deliberate owner-controlled rollout after complete gates, with rollback; Render auto-deploys `main`. Never merge experiments into `main` to run a test.
