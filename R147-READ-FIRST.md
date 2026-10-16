# FFH R147 — STAGING LOGIN PREP (zero-credit GitHub Pages path)
Date: 2026-10-17 JST. **Do not merge this branch into GitHub main.**

## Verified and implemented
- Hosted staging project `hlsjzjnondimwhqbgjqm` only: new `public.ffh_r147_member_preflight(text,text)` RPC, in isolated staging. No production changes.
- The RPC derives `auth.uid()` and the `auth.jwt().session_id` itself, checks the existing private FFH R146 Member/terms/status/session function, and verifies the canonical synthetic source using the private safe-source function. It never translates, approves, publishes, or writes data.
- `anon` EXECUTE=false, `authenticated` EXECUTE=true; no-JWT SQL returns `{status:denied,model_connected:false}`; both ordinary roles still have no direct sandbox schema usage.
- Tested staging Member is email-verified and has private profile, accepted staging terms and an actual Auth session. Positive caller RPC response HAS NOT YET been checked with a real browser bearer token.
- Supabase Edge Function `ffh-r147-member-test` was deployed as a first HTML callback concept. It is **UNUSABLE** as a browser login page: Supabase gateway forces `Content-Security-Policy: default-src 'none'; sandbox`, blocking scripts. Do NOT send users to that URL.
- REPLACEMENT: self-contained `docs/index.html` on **isolated public GitHub branch** `ffh-r147-hosted-member-auth-probe-20261017`, suitable for GitHub Pages. It uses only the staging public publishable API key, no service key, redirects magic link explicitly, clears URL token fragment immediately and stores the JWT only in page memory. `create_user:false` prevents signing up new users.
- GitHub Actions run [38978894918](https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38978894918) SUCCESS **10/10 static/negative checks**: valid JS, safe fixed staging URLs, no password/token persistence, no model dispatch, RPC refuses anonymous user, no sensitive client secret.
- **GitHub Pages IS NOT ENABLED yet.** User must enable in repository Settings > Pages > Deploy from a branch > `ffh-r147-hosted-member-auth-probe-20261017` > `/docs` > Save. After publishing, wait for actual URL confirmation before distributing.
- The target Pages URL is expected to be `https://easy123dcavers-ctrl.github.io/ffh-translation-service/` ONLY IF configured by GitHub as documented.
- In Supabase staging Auth > URL Configuration, add that exact GitHub Pages URI to Redirect URLs. Existing Site URL `http://localhost:3000` is broken for default invite; do not change production. The explicit `redirect_to` on OTP can succeed once allowlisted.
- Then on Android open Pages URL, submit the email owned by FFH owner, follow newly issued magic link, and observe `PASS: verified Member`. DO NOT paste JWT, magic link, or session ID into ChatGPT.
- **PASS on browser has not happened as of this handoff.** Real translation model remains disconnected; no fake translation outputs; future R148 must connect R145 protected broker to staged source and model, and validate quality separately.
- GitHub `main` confirmed unchanged at `5f8bcecba92653f653ef4514c6fcf32d9d6efbe9`, Render auto-deploy guard remains.

## Security and governance holds
Public GitHub Pages static frontend is intentionally public and uses a **publishable API key only**. The staging backend enforces signed-in role and session checks. The owner should confirm Pages settings point to the isolated branch and no other FFH content is published inadvertently.
The old staging security-advisor finding involving an unrelated anonymous-executable SECURITY DEFINER HTML-fragments function remains unmodified; separate impact review required.
The restricted durable R145 broker, 512MiB resource footprint, real hosted receipt/quota writer, security review, nine-language accuracy, fermentation safety gate, and Android/browser regression all remain release holds.
Do not claim this is a full hosted translation test; it is an authenticated **preflight path**.
