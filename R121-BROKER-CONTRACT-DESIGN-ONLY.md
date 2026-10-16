# FFH R121 — proposed trusted translation broker contract (DESIGN ONLY)
Date: 2026-10-16. No production deployment, secret, migration or schema mutation.

## Trust boundary
**Never** place the R119/R120 service bearer, Supabase `service_role` key, Render credentials, or other server secrets in Netlify HTML, JavaScript bundles, Android browser requests or public GitHub. The authenticated browser should call a server-side broker; the broker should call the guarded translator. R121's legacy staging quarantine is default-OFF, not a replacement for actual Member authorization.

### Public/guest path (proposed)
Guests receive published, already-reviewed multilingual content via the normal public FFH translation resolver. The server must not permit an anonymous or public browser to make arbitrary high-cost translation requests without explicit design and budgets. Fail safely to approved English text when a reliable reviewed translation is unavailable, according to FFH's agreed English-as-base display policy; never fabricate a reviewed translation.

### Authenticated Member path (proposed)
1. Browser sends an FFH Supabase Auth session token to an HTTPS broker endpoint. No shared translator credentials are exposed.
2. Broker verifies token signature against trusted Supabase Auth keys, audience, issuer, expiration/not-before, revocation behavior and relevant user state. **Verification must be implemented and reviewed by a qualified engineer**—do not trust a submitted `role`, `user_id` or translated text from the client.
3. Broker enforces Member/Moderator/Admin/Owner authorization and quota/rate/size/recency limits appropriate to the operation, using auditable server-side identity. Deny unauthenticated or suspended accounts according to actual FFH governance.
4. Broker checks source language, target mapping, content classification and exclusions; safety-protected or regulated source categories remain HOLD. Do not bypass Reviewed-state immutability or protected-source approval requirements.
5. Only then does the broker call the translation service using a server-held rotated secret. The staging/test secret is **not** a production authorization protocol.
6. Translator enforces fail-fast admission, input caps, protected tokens and conservative numeric/unit holds. It returns `held` or `provisional_candidate` only; **never approved** or automatically published.
7. Broker sanitizes and returns results and retry hints to the browser. Server-side ingest/approval, when desired, follows existing FFH authenticated governance with owner/staff review and audit records; there is no direct model→Reviewed write.

## Hard policy gates
- `POST /translate` and `POST /translate-batch` must not remain as a publicly accessible legacy bypass when the protected service is released. Retire, route through the broker, or reject.
- Never send member-private content into R102's shared cross-user cache. Avoid logging the request text, authorization header, batch text or privately identifiable identifiers in app logs, proxy logs and exception messages. Define encrypted transport, retention/deletion periods and audit access.
- Keep source text English canonical. Locale mapping `fil→tl` and `zh-Hans→zh` requires independent native-speaker/region script QA; Arabic must pass RTL layout checks; safety-critical numbers, temperatures, weights, ratios and shelf-life instructions require expert verification.
- Retries: at most three attempts, only retry genuine 429 after server's bounded Retry-After; never auto-retry `held`, 401, 400 or unknown failures. Avoid distributed retry storms through per-user quotas and jitter.
- Lock design: R120 `flock` is suitable for one Linux container only. Each extra Render replica or worker on separate hosts requires a distributed admission architecture and separate memory tests.
- Do not spend Netlify deployment credits or modify Supabase unless a reviewed implementation is ready for owner-approved release.

## Nonfunctional acceptance before any rollout
- Threat modeling covering stolen/expired tokens, token-revocation behavior, session confusion, CSRF/CORS, anonymous abuse, concurrency, HTTPS/TLS, WAF and rate limits.
- End-to-end Android/desktop staging with fake members and no real food-safety content; verify anonymous denial, role semantics, logout/revocation, quotas, replay limits, timeouts and human approval preservation.
- 512MiB *cold and warm* model testing at target CPU/memory; restart/worker recycle and lifecycle tests at production-equivalent startup command.
- Package-model archive SHA256 verification **before** unpack/install, code provenance/license and vulnerability review, source/lockfile SBOM, reproducible release artifacts and rollback checks.
- Qualified independent security/privacy review and native-language/fermentation scientific review, with findings explicitly resolved or held.

## Implementation status
NOT IMPLEMENTED. This is an engineering specification for the next authorized worker, not an assertion of current FFH capabilities or production readiness. No real FFH account data or secrets were accessed to create it.
