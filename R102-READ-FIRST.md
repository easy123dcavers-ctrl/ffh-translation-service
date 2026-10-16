# FFH R102 — READ FIRST — Opt-in translation cache prototype

Date: 2026-10-16
Branch: ffh-r102-optin-cache-prototype-20261016
Production status: NOT DEPLOYED. NOT APPROVED FOR MERGE.

## Verified
- GitHub run: https://github.com/easy123dcavers-ctrl/ffh-translation-service/actions/runs/38830318784
- 9/9 offline stdlib cache contract tests PASSED; app.py and cache module syntax checks passed.
- Files: translation_cache.py (new), app.py (three narrow modifications), tests/test_r102_cache.py (new), workflow (new).
- R101 validated 120 cached hits for 240 repeated synthetic occurrences on each of two machines, reducing translation step time by approximately 2x *for a 50%-duplicate dataset*.
- R101 peak process memory >915 MB on each GitHub runner. Historical Render free worker memory is about 512 MB; DO NOT assume this stack is safe there.

## Cache scope / limits
- Cache is OFF by default, controlled only by FFH_TRANSLATION_CACHE_ENABLED=true after full approval.
- In-memory and process-local, never disk/database. Max 128 exact strings, 600-second TTL.
- Skip input longer than 512 characters and output longer than 4096 characters.
- Key: exact source text, source language, target language, FFH_TRANSLATION_CACHE_GENERATION.
- No transient errors, non-text, empty results, or failed translations are cached.
- Thread-safe cache access, but translation work is not serialized; duplicate requests may concurrently calculate on cache miss.
- Model is not loaded by this cache. Restart on model replacement, or explicitly change generation and clear cache.
- API routes, request/response payloads, auth, MAX_BATCH_ITEMS=25, render.yaml, models and package requirements left unchanged.

## Mandatory next checks BEFORE merge, approval or production deployment
1. Full service integration with installed Argos model on memory-constrained replica; verify /translate and /translate-batch 400/500 response behavior, target handling and per-item failures with cache OFF and ON.
2. Confirm real FFH input privacy rules. In-memory caching of any member-private strings is NOT approved; add explicit non-sensitive input classification or exemption before enabling.
3. Measure CPU, peak RSS, cold/warm latency, cache hit rate, TTL and eviction under real representative multilingual workloads, without production writes. Confirm the service remains under Render's actual memory cap.
4. Safety terms and fermentation-specific instructions require domain-qualified review; all machine outputs remain provisional, especially safety-restricted sources.
5. Verify no interaction with Supabase approval gates, RLS, published content, site search language persistence, Netlify, or FFH reviewed-state immutability.
6. Revisit 25-item batch limit only after request profiling and failure recovery are demonstrated. Do not multiply Gunicorn workers against the 512 MB cap.
7. Have a second worker review the diff, regression checklist and release plan. Owner retains deployment control.

## Reproduction
GitHub Actions workflow is isolated, standard-library-only, and never contacts FFH production.
Run locally: python -m unittest discover -s tests -p 'test_r102_cache.py' -v
