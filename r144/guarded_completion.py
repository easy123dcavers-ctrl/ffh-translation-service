"""R145: final authorization/safety gate precedes the permanent 'done' receipt.

Staging-only. The original R139 PostgresAtomicLedger, atomic quota admission,
and R136 Broker remain unchanged. Per-submit receipt facade defers only the
successful terminal 'done' transition. Mid-request revoked access or protected
sources finalize 'held' instead; uncertain finalization denies without replay.
A committed 'done' means server-authorized response, not proof of HTTP receipt.
"""
from __future__ import annotations
from r136.broker import Broker, Denied, Verdict, User, MEMBER_ROLES
from r139.postgres_ledger import make_staged_postgres_broker

class _DeferredReceiptLedger:
    """Per-request facade, never a shared mutable singleton."""
    def __init__(self, real):
        self.real = real
        self.owner = None
        self.nonce = None
        self.pending_done = False
        self.settled = False

    def admission(self, owner, nonce, payload_digest):
        if self.owner is not None:
            raise Denied(503, "request ledger reused")
        self.real.admission(owner, nonce, payload_digest)
        self.owner, self.nonce = owner, nonce

    def finish(self, owner, nonce, state):
        if self.owner != owner or self.nonce != nonce or self.settled or self.pending_done:
            raise Denied(503, "receipt transition refused")
        if state == 'done':
            self.pending_done = True
            return
        self.real.finish(owner, nonce, state)
        self.settled = True

    def finalize(self, state):
        if not self.pending_done or self.settled or state not in ('done', 'held'):
            raise Denied(503, "no pending provisional draft")
        # R139.finish has conditional WHERE state='inflight'. Never retry
        # if COMMIT status is unknown: the existing nonce remains a tombstone.
        self.real.finish(self.owner, self.nonce, state)
        self.pending_done = False
        self.settled = True

class GuardedBroker:
    def __init__(self, core, verify, classify):
        self.core, self.verify, self.classify = core, verify, classify

    def submit(self, bearer, request):
        receipt = _DeferredReceiptLedger(self.core.ledger)
        runner = Broker(self.core.verifier, self.core.classify,
                        self.core.translate, receipt, self.core.quota)
        result = runner.submit(bearer, request)
        try:
            try:
                member = self.verify(bearer)
            except Exception:
                raise Denied(503, "final Member validation unavailable") from None
            if (not isinstance(member, User) or not member.enabled or
                member.role not in MEMBER_ROLES or member.user_id != receipt.owner):
                raise Denied(403, "Member eligibility changed; withhold output")
            try:
                still = self.classify(request['text'])
            except Exception:
                raise Denied(503, "final source classification unavailable") from None
            if not isinstance(still, Verdict) or still.allowed is not True:
                raise Denied(422, "source became protected; withhold output")
        except Denied:
            if receipt.pending_done:
                receipt.finalize('held')
            raise
        if result['status'] == 'provisional_candidate':
            receipt.finalize('done')
        elif result['status'] != 'held' or not receipt.settled:
            raise Denied(503, "unfinalized receipt; withhold response")
        return result

def make_guarded_broker(verifier, classify, translate, connect, secret,
                        *, max_per_window=3, window_seconds=60):
    if not callable(verifier) or not callable(classify) or not callable(translate):
        raise ValueError("trusted adapters required")

    def checked_translate(target, text):
        try:
            eligible = classify(text)
        except Exception:
            return {'status': 'held', 'human_approved': False, 'production_writes': 0}
        if not isinstance(eligible, Verdict) or eligible.allowed is not True:
            return {'status': 'held', 'human_approved': False, 'production_writes': 0}
        result = translate(target, text)
        # Mid-translation source reclassification is a terminal HOLD.
        try:
            eligible = classify(text)
        except Exception:
            return {'status': 'held', 'human_approved': False, 'production_writes': 0}
        if not isinstance(eligible, Verdict) or eligible.allowed is not True:
            return {'status': 'held', 'human_approved': False, 'production_writes': 0}
        return result

    core = make_staged_postgres_broker(verifier, classify, checked_translate,
                                       connect, secret, max_per_window=max_per_window,
                                       window_seconds=window_seconds)
    return GuardedBroker(core, verifier, classify)
