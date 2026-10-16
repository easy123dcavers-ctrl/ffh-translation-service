"""R144 staging-only post-translation source/Member revalidation.

R139's original Broker validates source and member BEFORE dispatch. Its
transport callback does not know bearer token and by itself cannot prove that
a now-suspended member, revoked session or newly protected source remains
eligible to RECEIVE a draft. This narrowly composed wrapper fails closed.
It does not auto-publish or write any FFH content. Durable receipts remain
under the original unchanged R139 PostgresAtomicLedger transaction.

A double-check after dispatch can only WITHHOLD output; it cannot undo an
already-run model. Asynchronous job systems need the same release gate.
"""
from __future__ import annotations
from r136.broker import Denied,Verdict,User,MEMBER_ROLES
from r139.postgres_ledger import make_staged_postgres_broker

class GuardedBroker:
    def __init__(self,core,verify,classify):
        self.core,self.verify,self.classify=core,verify,classify
    def submit(self,bearer,request):
        result=self.core.submit(bearer,request)
        # Auth must be fetched AGAIN from online GoTrue; never cache claims.
        try:
            member=self.verify(bearer)
        except Exception:
            raise Denied(503,"final Member validation unavailable") from None
        if not isinstance(member,User) or not member.enabled or member.role not in MEMBER_ROLES:
            raise Denied(403,"Member eligibility changed; withhold output")
        # Source can be protected in the middle of inference.
        try:
            still=self.classify(request["text"])
        except Exception:
            raise Denied(503,"final safety classification unavailable") from None
        if not isinstance(still,Verdict) or still.allowed is not True:
            raise Denied(422,"source became protected; withhold output")
        return result

def make_guarded_broker(verifier,classify,translate,connect,secret,
                        *,max_per_window=3,window_seconds=60):
    if not callable(verifier) or not callable(classify) or not callable(translate):
        raise ValueError("trusted adapters required")
    def checked_translate(target,text):
        try:
            eligible=classify(text)
        except Exception:
            # The original broker accepts 'held' as terminal; do not produce draft.
            return {"status":"held","human_approved":False,"production_writes":0}
        if not isinstance(eligible,Verdict) or not eligible.allowed:
            return {"status":"held","human_approved":False,"production_writes":0}
        result=translate(target,text)
        # Post-inference check before original broker classifies any output.
        try:
            eligible=classify(text)
        except Exception:
            return {"status":"held","human_approved":False,"production_writes":0}
        if not isinstance(eligible,Verdict) or not eligible.allowed:
            return {"status":"held","human_approved":False,"production_writes":0}
        return result
    core=make_staged_postgres_broker(verifier,classify,checked_translate,connect,secret,
                                     max_per_window=max_per_window,
                                     window_seconds=window_seconds)
    return GuardedBroker(core,verifier,classify)
