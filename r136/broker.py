"""FFH R136 isolated broker *domain contract* (no web server or prod wiring).

Security posture: fail closed; allow only exact server-curated normal non-safety
English sources. Live Member authorization and model transport are INJECTED by
trusted server adapters, never inferred from browser-submitted claims.
All model results remain provisional/held. No DB writes to FFH are supported.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import re
import sqlite3
import threading
import time
from typing import Callable

TARGETS = frozenset(("es", "fr", "ja", "de", "ar", "tl", "ko", "vi", "zh"))
LOCALES = {"fil": "tl", "zh-Hans": "zh"}
MEMBER_ROLES = frozenset(("Member", "Moderator", "Admin", "Owner"))
KEY_RE = re.compile(r"^[a-zA-Z0-9_-]{16,96}$")

class Denied(Exception):
    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason

@dataclass(frozen=True)
class User:
    user_id: str
    # This MUST come from a fresh, trusted role resolver, NOT the request body,
    # user_metadata or an unsigned claim.
    role: str
    enabled: bool = True

@dataclass(frozen=True)
class Verdict:
    # Server-side classification from the canonical English source registry.
    allowed: bool
    reason: str = ""

class MemoryQuota:
    """Single-process bounded admission only; not a distributed quota store."""
    def __init__(self, max_per_window: int = 3, window_seconds: int = 60,
                 clock: Callable[[], float] = time.monotonic):
        self.max_per_window = max_per_window
        self.window_seconds = window_seconds
        self.clock = clock
        self._lock = threading.Lock()
        self._usage: dict[str, list[float]] = {}
    def check(self, user_id: str) -> bool:
        now = self.clock()
        with self._lock:
            usage = [t for t in self._usage.get(user_id, ()) if now - t < self.window_seconds]
            if len(usage) >= self.max_per_window:
                self._usage[user_id] = usage
                return False
            usage.append(now)
            self._usage[user_id] = usage
            return True

class ReceiptLedger:
    """Durable, no-plaintext receipts. On restart, stale in-flight is UNKNOWN.

    This ledger is fit for a disposable single-process SQLite harness only,
    NOT multiple Render replicas, shared NFS, or an FFH production queue.
    """
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False,
                                   isolation_level=None, timeout=5)
        self.lock = threading.RLock()
        self.conn.execute('PRAGMA busy_timeout=5000')
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('''CREATE TABLE IF NOT EXISTS receipt(
            request_hash TEXT PRIMARY KEY, payload_hash TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('inflight','unknown','done','held')),
            created_at INTEGER NOT NULL)''')
        # After any interpreter crash, dispatch may have happened: NO REPLAY.
        self.conn.execute("UPDATE receipt SET state='unknown' WHERE state='inflight'")
    def admission(self, owner: str, nonce: str, payload_digest: str) -> None:
        request_hash = sha256((owner+"\0"+nonce).encode()).hexdigest()
        with self.lock:
            row = self.conn.execute('SELECT payload_hash, state FROM receipt WHERE request_hash=?',
                                    (request_hash,)).fetchone()
            if row:
                if not hmac.compare_digest(row[0], payload_digest):
                    raise Denied(409, "idempotency key was reused for different content")
                raise Denied(409, "request already seen; never replay an unknown outcome")
            self.conn.execute('INSERT INTO receipt VALUES (?,?,?,?)',
                              (request_hash, payload_digest, 'inflight', int(time.time())))
    def finish(self, owner: str, nonce: str, state: str) -> None:
        assert state in ('unknown','done','held')
        request_hash = sha256((owner+"\0"+nonce).encode()).hexdigest()
        with self.lock:
            self.conn.execute("UPDATE receipt SET state=? WHERE request_hash=? AND state='inflight'",
                              (state, request_hash))
    def close(self): self.conn.close()

class Broker:
    def __init__(self, verifier: Callable[[str], User | None],
                 classify: Callable[[str], Verdict],
                 translate: Callable[[str, str], dict],
                 ledger: ReceiptLedger, quota: MemoryQuota):
        self.verifier, self.classify, self.translate = verifier, classify, translate
        self.ledger, self.quota = ledger, quota
    def submit(self, bearer: str, request: dict) -> dict:
        if not isinstance(bearer, str) or len(bearer) > 8192 or not bearer:
            raise Denied(401, "invalid authorization")
        try:
            user = self.verifier(bearer)
        except Exception:
            raise Denied(503, "identity verification unavailable") from None
        if not isinstance(user, User) or not user.enabled or user.role not in MEMBER_ROLES:
            raise Denied(403 if isinstance(user, User) else 401, "member authorization denied")
        if not isinstance(request, dict) or set(request) != {"source", "target", "text", "request_id"}:
            raise Denied(400, "invalid request schema")
        source, target, text, nonce = (request[x] for x in ("source","target","text","request_id"))
        if source != "en" or not isinstance(target,str):
            raise Denied(400, "English canonical source and target required")
        canonical_target = LOCALES.get(target,target)
        if canonical_target not in TARGETS:
            raise Denied(400, "unsupported language")
        if not isinstance(text,str) or not (1 <= len(text) <= 500) or text != text.strip():
            raise Denied(400, "invalid source text")
        if any(ord(c) < 32 and c not in '\n\t' for c in text):
            raise Denied(400, "invalid control characters")
        if not isinstance(nonce,str) or not KEY_RE.fullmatch(nonce):
            raise Denied(400, "invalid idempotency key")
        # NEVER use browser-supplied safety classification. This callback must
        # query an independently curated, current English canonical registry.
        try:
            classification = self.classify(text)
        except Exception:
            raise Denied(503, "source registry unavailable") from None
        if not isinstance(classification,Verdict) or not classification.allowed:
            raise Denied(422, "source not approved for automatic provisional drafting")
        payload_hash=sha256(json.dumps(["en",canonical_target,text],ensure_ascii=False,
                                       separators=(',',':')).encode()).hexdigest()
        # Quota consumed before DB commit and transport; no fallback if denied.
        if not self.quota.check(user.user_id):
            raise Denied(429, "member request quota exceeded")
        self.ledger.admission(user.user_id,nonce,payload_hash)
        try:
            result=self.translate(canonical_target,text)
        except Exception:
            self.ledger.finish(user.user_id,nonce,'unknown')
            raise Denied(502, "translation outcome unknown; do not replay") from None
        if not isinstance(result,dict) or result.get('status') not in ('held','provisional_candidate'):
            self.ledger.finish(user.user_id,nonce,'unknown')
            raise Denied(502, "translator returned untrusted result")
        # Any attempt by a model transport to assert review/publication is an
        # invariant violation, not a user-facing approval.
        if result.get('human_approved') is True or result.get('production_writes',0) != 0:
            self.ledger.finish(user.user_id,nonce,'unknown')
            raise Denied(502, 'model cannot approve or publish content')
        if result['status']=='held':
            self.ledger.finish(user.user_id,nonce,'held')
            return {'status':'held','human_approved':False,'retryable':False}
        draft=result.get('draft')
        if not isinstance(draft,str) or not draft.strip() or len(draft)>3000:
            self.ledger.finish(user.user_id,nonce,'unknown')
            raise Denied(502, "translator returned invalid provisional draft")
        self.ledger.finish(user.user_id,nonce,'done')
        return {'status':'provisional_candidate','draft':draft,
                'human_approved':False,'production_writes':0}
