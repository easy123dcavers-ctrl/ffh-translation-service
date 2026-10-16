# FFH R130 — owner-authorized 10% RAM reserve, conditional on stability

**Decision (2026-10-17):** FFH owner explicitly approved lowering the *isolated translator experiment's* required memory headroom from 20% to **10%, if it holds**. Do not construe this as approval to deploy, retry production jobs, relax translation safety, change Supabase, or spend on higher-tier infrastructure.

## Exact resource acceptance (ALL gates; no averaged or rounded pass)

- Cgroup: exactly **512 MiB**, zero swap, **0.1 CPU** maximum, isolated single active model worker, network disabled.
- Peak cgroup memory, including page cache and model files: **10 * peak_bytes <= 9 * (512*1024*1024)**. That is at least 10% reserve; maximum **460.8 MiB**.
- Zero cgroup OOM kills; strict negative result if memory peak breaches once, even if a later period is healthier.
- At least **1800 monotonic seconds** of real Argos load, **>=2 complete nine-language circuits** with German on >=2, no concurrent models and all nine accounted for.
- Real crash witness: SIGKILL one inflight backend; gateway returns 502 UNKNOWN, non-retryable, never auto-replay.
- Verify handoff/overload/legacy/auth semantics with 503/Retry-After, 429, 410, and unauthorized 401; no approval or production writes.
- Pin to R125F source Git blob `a73832312115cc02c019cb1fa2e8edd457c7654b`; verify all nine installed Argos model file trees at Docker build.
- Passing this suite is **resource-only**, not readiness for a public Member broker or production.

## Real evidence before policy change

- R129 25-item Spanish batch: 459.51 MiB peak; 10.25% headroom; zero OOM; 41.7 seconds — passes only the newly accepted 10% instantaneous memory *threshold*.
- R129 five-item Spanish batch: 461.37 MiB peak; 9.89% headroom; zero OOM; 18.2 seconds — fails the strict 10% threshold.
- Neither previously demonstrated 30-minute stability or a complete nine-language circuit. DO NOT mark either as certification.

## Implementation and status references

- New branch: `ffh-r130-ten-percent-endurance-20261017`, unrelated to Render `main`.
- New exact byte-level gate: `tests/r130_memory_policy.py`; original `tests/r123h_memory_policy.py` retains the historical 20% standard.
- Generator: `r130/prepare_endurance.py`, reuses verified R129 30-minute source transformations and selects R130 10% gate.
- New workflow: `.github/workflows/ffh-r130-ten-percent.yml`.
- GitHub Actions run: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38942467399
- Older 20%-policy caching diagnostic: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38941241901
- **At handoff time:** R130 run started and entered the real nine-model build. Check actual current run status and summary evidence before claiming a PASS. Do NOT treat a build success or job start as endurance pass.

## Project protection

No Render service, Netlify, Supabase production, or GitHub default-branch changes permitted in this ticket. If resources fail under 10%, preserve the failure, investigate model lifecycle, cache, model variant and CPU/memory tradeoffs without silently raising limits or removing safety checks. Existing translation jobs (131 completed, 615 failed, 156 pending at last read-only checkpoint) must not be replayed as part of this experiment.
