"""R119 staging HTTP-429 policy specification (NOT wired to live FFH clients).

Treat every translation request as at most three total attempts. Stop immediately
on anything other than HTTP 429 (including 401/400/held/success). Never retry
after an unbounded delay. The caller must request user confirmation for a
further retry, never loop forever or send member text to a shared cache.
"""
from __future__ import annotations

MAX_TOTAL_ATTEMPTS = 3
MAX_ONE_DELAY_SECONDS = 4.0
MAX_TOTAL_SLEEP_SECONDS = 6.0

def next_retry_delay(status, retry_after, *, attempt_index, already_slept=0.0):
    """Return seconds to wait or None (stop). First request index=1."""
    if status != 429 or not 1 <= attempt_index < MAX_TOTAL_ATTEMPTS:
        return None
    if not isinstance(already_slept, (int, float)) or already_slept < 0:
        return None
    if not isinstance(retry_after, str):
        return None
    if not retry_after.isascii() or not retry_after.isdecimal():
        return None
    delay = float(retry_after)
    if not 0 < delay <= MAX_ONE_DELAY_SECONDS:
        return None
    if already_slept + delay > MAX_TOTAL_SLEEP_SECONDS:
        return None
    return delay


def classify_response(status, body, *, attempt_index, retry_after=None, already_slept=0.0):
    """Return deterministic guidance, without initiating any network requests."""
    # Held is always final; do not retry to evade review/safety restrictions.
    if isinstance(body, dict) and body.get("status") == "held":
        return {"action": "hold_for_review"}
    if status == 200:
        return {"action": "return_provisional_only"}
    delay = next_retry_delay(
        status, retry_after, attempt_index=attempt_index,
        already_slept=already_slept
    )
    if delay is not None:
        return {"action": "retry_after", "delay_seconds": delay}
    return {"action": "stop_and_notify"}
