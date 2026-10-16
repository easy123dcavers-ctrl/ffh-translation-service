# FFH R123H — MINIMUM 20% MEMORY HEADROOM — READ FIRST
Date: 2026-10-16. **EXPERIMENTS ONLY. Production release remains HOLD.**

## Decision
From this experimental milestone forward, require **at least 20% RAM headroom** when testing the single-model FFH translator in an enforced **512 MiB RAM+swap container**. This permits a peak of **no more than 409.6 MiB**, with **zero** out-of-memory kills. This policy replaces the historical exploratory 15% minimum for any *new* candidate; old tests are not retroactively certified. Compute the gate using exact unrounded cgroup bytes: `peak_bytes * 5 <= limit_bytes * 4`, plus `oom_kills == 0`. Never change the production memory limit or weaken acceptance gates to make CI pass.

### Verified raw outcomes — all used German en→de, Argos batch size 1
| Run | Beam | Peak RAM | Headroom | Full 25-item batch entries | Outcome |
|---|---:|---:|---:|---:|---|
| [initial 20% test](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38862940344) | 4 | **512.00 MiB** | **0%** | 0 | **FAIL** first batch, OOM kill=1 |
| [profile sweep](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38863208567) | 4 repeat | **512.00 MiB** | **0%** | 0 | **FAIL** first batch, OOM kill=1 |
| Same profile sweep | **2** | **283.85 MiB** | **44.56%** | 375 | **PASS** strict 20% gate |
| Same profile sweep | **1** | **293.50 MiB** | **42.68%** | 450 | **PASS** strict 20% gate |
| [independent repeat](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38863598097) | **2** | **281.06 MiB** | **45.10%** | 350 | **PASS** strict 20% gate |

**Preferred experimental configuration** for German: `ARGOS_BATCH_SIZE=1` and `ARGOS_BEAM_SIZE=2`. Two independent isolated tests passed. `ARGOS_BEAM_SIZE=4` is on HOLD after two separate cold first-batch OOM kills in this same test branch, despite an earlier R123 successful run with 44.41% headroom. Beam 1 passes the resource gate once but may change linguistic quality and is not the default recommendation.

### Actual safety/API work verified under beam 2
- Real Argos + Flask/Gunicorn under 512MiB hard Docker limit, one CPU, one model, one worker/2 threads, loopback gateway and no runtime network.
- First pass: 375 synthetic batch items, 15 accepted 25-item batches; 15/15 concurrent requests rejected HTTP 429; three controlled master restarts, explicit 503 during gaps, no gateway transport errors, zero OOM.
- Confirmatory pass: 350 synthetic items, 14 accepted 25-item batches; 14/14 competing 429, three controlled restarts, zero OOM, zero model/gateway transport errors. 322 provisional only and 28 held without drafts. No approved translations.
- Eleven new standard-library policy boundary tests PASS; checks include exact 20% cutoff, rejection one byte above, wrong cgroup size, and OOM rejection even with low usage.
- The **beam2 and beam1 outputs have NOT been reviewed by qualified German speakers** and may differ materially from beam4. A resource pass does not authorize translation ingestion, human-reviewed-state changes or food safety claims.
- Real production Render configuration, traffic and cold-start behavior are NOT represented sufficiently by two ~2-minute isolated runs; longer diverse restart/soak validation remains a release requirement. The other eight target-language models must also be retested under the new threshold rather than relying solely on historical runs.

## Code and reproducibility
Branch: `ffh-r123h-headroom20-20261016`, derived from `ffh-r123-loopback-drain-gateway-20261016`. All commits confined to this test branch.
- `tests/r123h_memory_policy.py`: exact integer resource admission check, fixed 512MiB limit, >=20% reserve, zero OOM.
- `tests/test_r123h_20pct_headroom.py`: 11 boundary tests.
- `tests/r123_gateway_real_soak.py`: calls new policy and reports min 20%, allowed 409.6 MiB and actual cgroup peak before deciding PASS/HOLD.
- `tests/r123.Dockerfile`: includes new checker.
- `.github/workflows/ffh-r123h-headroom20.yml`: initial real and standalone offline tests.
- `.github/workflows/ffh-r123h-profile-sweep.yml`: real German beam4 repeat, beam2, beam1 matrix; one overall workflow conclusion FAIL because beam4 failure is correctly preserved.
- `.github/workflows/ffh-r123h-beam2-repeat.yml`: second fresh German beam2 confirmation.
- GitHub Actions synthetic diagnostic ZIPs are archived in the companion MC handoff, including both failures, no source/private FFH content. Link to this report and artifact numbers in ZIP.

## Explicit limitations and release blockers
1. Do NOT merge experiments into Render auto-deployed `main`, and do not update production Render, Netlify, Supabase or Reviewed translations.
2. Site-wide 20% is now a **test acceptance policy proposal**, not a production setting or guarantee that every language can meet it. At 512MiB, translation service peak must remain <=409.6MiB.
3. The German lower-beam profile needs independent linguistics and fermentation-safety QA; changed search width can change meaning, including critical numbers/units. All outputs remain provisional or held.
4. R123 gateway is loopback/test-only; Member auth, broker secrets, rate limiting, legacy route retirement, crash recovery and multi-replica management remain release blockers.
5. Argos model archive hash verification *before* installation, licensing and dependency security audit, unexpected crash response, and 30+ minute production-shaped load tests remain uncompleted.
6. Do not apply the German beam2 profile blindly to Tagalog/Korean/other models; each language needs independent headroom and translation fidelity checks. Maintain known Tagalog/Korean batch1 restrictions.

**PRODUCTION RELEASE STATUS: HOLD. ZERO Netlify deployments, Supabase writes, automatic approvals, and Render changes.**
