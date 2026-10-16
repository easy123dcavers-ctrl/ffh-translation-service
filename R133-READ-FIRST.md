# FFH R133 — forensic-only, zero-retraining checkpoint

Date: 2026-10-17. Read `R132-READ-FIRST.md`, `R131-READ-FIRST.md`, and `R130-READ-FIRST.md` in order.

## Why R133 exists

R132 single-flight gateway's atomic 429 correctness tests PASSED, but its real-model endurance run **FAILED the owner's 10% memory headroom requirement**:
https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38946255555

- R132 peak cgroup memory **495.07 MiB**, only **3.31% spare** of 512MiB; zero OOM kills; 106.71s wall.
- R132 Spanish stage: 2 batches, 50 real synthetic items, last peak **458.73 MiB**. Korean stage: 1 batch, 25 items, last peak **495.07 MiB**. 75 items total.
- Gateway reported 3 explicit busy 429s; **the atomic single-flight 429 fix held**. No data writes.
- Previous R129 nine-model test with no runtime tree rehash was **SUCCESS** at 283.79MiB, 44.57% spare, 753.3s; R130 longer test with full tree rehash reached **290.0MiB**, 43.36% spare before failing a concurrency timing assertion at 887.31s. So hashing cannot be asserted as the *sole* explanation; memory behavior is variable.
- **NEVER** describe 30-minute stability as proven or call the service production-ready.

## R133 diagnostic mechanics

- Experimental branch `ffh-r133-memory-components-20261017`; GitHub default `main` / Render production untouched.
- `r133/prepare_diagnostic.py` derives from exact pinned R125F through R132 and adds read-only cgroup memory.stat snapshots at model startup, after health, after batch, and after exit.
- Cgroup component keys: anon, file, kernel, slab, shmem, pagetables, kernel_stack, sock, file_mapped, inactive_file, active_file. Memory.current and memory.peak also recorded.
- The synthetic real-Argos diagnostic runs only **es and ko** model targets for a deliberately shorter bounded test; the Docker image still builds and SHA256 verifies **all nine installed model trees**. All 512MiB/0.1CPU/10% memory tripwires remain intact. This is a **diagnostic-only** run and cannot approve a nine-model 30-minute release.
- Workflow `.github/workflows/ffh-r133-memory-diagnostic.yml` and tests `tests/test_r133_generator.py`.
- GitHub Actions latest R133 run https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38947255824 . This URL might not have completed at this handoff: inspect actual result before making a factual claim.
- Parallel original R131 endurance run https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38943614131 should also be checked, with exact summary/artifact evidence.

## Safety and next actions

1. Read R133 result and compare actual cgroup peak and memory.stat `anon`/`file` BEFORE load, after health, after translation, and after stop; classify dominant delta. Some cgroup stats and cumulative peak are not directly additive—avoid simplistic comparisons.
2. If R133 is resource HOLD, do not relax the owner's 10% standard, CPU 0.1, 512MiB nor hide failure as random; isolate a repeatable source of the extra ~200MiB. Compare pinned Python/Argos versions, backend import/loading lifecycle and model variant.
3. Only rerun full 30-minute nine-model resource acceptance once the memory issue is understood or addressed. Existing R129 short test is not sufficient.
4. Keep CI branch isolated; avoid pushing to main, Netlify, Render or writing Supabase. Machine output remains provisional; Member Auth broker and human safety QA required prior to release.
5. FFH owner wants maximum independent verified progress, updates with completed/total/remaining, consolidated ZIP on completed milestone, minimal Android actions.

**Previous production job backlog at last read-only check:** 131 completed, 615 failed, 156 pending. No production retries, approvals, or migrations are authorized in this diagnostic.
