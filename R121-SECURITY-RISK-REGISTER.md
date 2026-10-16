# FFH R121 — Security and supply-chain audit (engineering review, not external certification)
Date: 2026-10-16

## Assessment basis
Read-only inspection of the R120/R121 translation service source, Render build instructions and exact Argos upstream release. This is **our internal engineering review**, NOT an independent third-party penetration test, legal license opinion, or authoritative threat model. Source provenance:
- Isolated branch: `ffh-r121-legacy-quarantine-security-audit-20261016`.
- Pinned Argos code revision: `63b84ecb46c740c7a7c066d58636434d3e893ebf` (v1.11.0).
- Upstream license: https://raw.githubusercontent.com/argosopentech/argos-translate/63b84ecb46c740c7a7c066d58636434d3e893ebf/LICENSE — MIT for **this source code**.
- Pinned Argos *package-index snapshot*: https://raw.githubusercontent.com/argosopentech/argospm-index/ff90de60728f7c1338ff6b75974e4c89b2442d22/index.json
- Original requirements allow mutable transitive dependencies (`spacy`, `packaging`, `minisbd`, several version ranges), even with pinned Argos source revision. The test image presently installs those dependencies at build time.
- Model-index records observed here contain version, language pair, and links but **no independently authenticated model-archive SHA256 or license declaration**. This audit makes no legal assertion about model usage.

## Findings: prioritized, actionable
| ID | Priority | Verified issue | Minimum preproduction acceptance |
|---|---|---|---|
| SEC-01 | BLOCKER | The legacy `POST /translate` and `POST /translate-batch` routes remain reachable without the R119 guarded bearer/approval/admission controls. | Replace with audited member-scoped broker route or retire them; no unguarded fallback. Stage-only R121 quarantine is a test mechanism, OFF by default. |
| SEC-02 | BLOCKER | R119 staging shared bearer is not FFH Member/Owner identity. Exposing it in the Netlify browser would disclose a reusable secret. | A trusted server-side broker validates a genuine FFH member session/JWT, authorization, quotas and safety gates, stores secrets only server-side, then calls protected translation service. No secret in HTML/JS. |
| SEC-03 | HIGH | `install_models.py` calls a live, mutable public index, downloads a model and installs it *before* the R119 post-install observed-tree hash check. | Download from an approved immutable target, verify **archive SHA256 BEFORE opening/installing**, verify model licensing and source provenance, quarantine unexpected files and fail closed. |
| SEC-04 | HIGH | The Argos test fork has not received independent packaging/security review; dependencies are not fully pinned with reproducible wheel digests. | Security/license review of source diff, audited lockfile with hashes, verified build attestations and patch maintenance policy. |
| SEC-05 | HIGH | Admission file lock is local to a single Linux container. Multi-replica deployment, service replacements, or old legacy paths can bypass local contention. | Define single-instance deployment invariant or use correctly managed distributed rate/admission; test concurrent replacements and forced termination. |
| SEC-06 | HIGH | Member data policy for translation text, logs and retention is not verified. Stack traces on legacy exception paths and proxy logs must be audited. | Minimal request logging, redaction, no cross-user cache, retention limits, secrets in protected runtime configuration, privacy impact review with real architecture. |
| SEC-07 | HIGH | Guarded staging has no member-level identity, differentiated quotas, abuse throttling, or publicly reviewed authorization. Its 429 is resource admission only. | Broker-enforced identity/rate limits, payload validation, explicit security and request billing budgets, and abuse tests. |
| SEC-08 | HIGH | Human translation correctness/safety review has not occurred across all languages; provisional output cannot be auto-approved. | Independent fluent-person and fermentation-safety review, protected-source exclusions, Reviewed-state immutability, documented final editorial authority. |
| SEC-09 | MEDIUM | Render `render.yaml` defines one Gunicorn worker **and one thread**, while R118–R120 experimental tests use one worker **and two threads**. | Production-equivalent staging command/restarts/memory validation. Never copy CI performance claims directly onto current Render configuration. |
| SEC-10 | MEDIUM | R120 lock in `/tmp` is protected with O_NOFOLLOW + ownership check but a pre-existing owned file's permission bits/hardlinks are not yet independently audited. | Controlled writable directory, regular-file owner/mode checks, ownership/permissions tests, and container lifecycle review. |
| SEC-11 | MEDIUM | R119 429 retry reference is not integrated into the FFH client. Retry storms and UX under sustained overload have not been tested on mobile. | Backoff with at most 3 attempts; stop on holds/auth errors; Android/mobile tests; limit aggregate retries across clients. |
| SEC-12 | MEDIUM | R119 tree digests prove similarity to R113 test files, not publisher authenticity. Model archive licensing differs from Argos software licensing. | Independent model archive provenance and license confirmation before any distribution or public use. |

## R121 mitigation already isolated (NOT deployed)
`FFH_LEGACY_QUARANTINE_STAGING_ONLY=true`, together with `FFH_GUARDED_API_STAGING_ONLY=true`, disables only the old POST translation routes (410). **Both flags are required**; they are false by default and they are not a production authorization substitute. It leaves `/health`, `/languages` and staging-guarded endpoints working. The corresponding 98 regression tests passed in the isolated GitHub workflow (run https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38855775669).

## Real-model acceptance currently under investigation
First hard-512MiB German staging quarantine test run https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38855947860 **FAILED**: 512 MiB cgroup peak and OOM kill=1 during the first guarded 25-item batch, despite earlier 2-minute warm tests passing. It passed the four legacy-bypass denials, 401 and held-URL assertions *before* the OOM. Record as **HOLD**, not evidence of a deployable 512MiB cold start. More isolation under branch `ffh-r121b-coldstart-memory-20261016`.

## Recommended server-side broker design (UNIMPLEMENTED)
1. Android/desktop browser uses current authenticated FFH session to call a trusted *server-side* translation broker (e.g. Supabase Edge Function if its security model/limits are approved; this is only a design option, not an implementation).
2. The broker validates session JWT against trusted Supabase Auth keys, user role/access, abuse limits, maximum payload lengths, source/target allowlist and safety-source classification, **without exposing any shared service secret in browser code**.
3. Broker uses a short-retention privacy policy and a private runtime secret to contact the guarded model API; never emit credentials or member text into logs.
4. Results return **provisional/held only**; the existing English-first translation memory and Owner/Admin safety review determine if a value can ever become Reviewed or public. No direct browser ingestion or writing Reviewed state.
5. Stage with dummy accounts and invented texts, test end-to-end authentication/revocation, CSRF/CORS behavior, server-side quotas, failure/retry/rollback, idle cold start and Render 512 MiB budget. Obtain independent security + linguistic sign-off before deployment.

## Release verdict
**HOLD / NOT APPROVED FOR PRODUCTION.** No Render, Supabase, Netlify or production changes were made by R121. Do not merge experimental GitHub branches into `main`, since Render auto-deploys it. Maintain the stop gates until independently verified.
