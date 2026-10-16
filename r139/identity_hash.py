"""Privacy-preserving stable identifiers for staging ledger and quota receipts.

Secret never leaves the server. Rotate only with explicit tombstone migration;
rotation without preserved old keys can let an old request_id replay.
"""
from __future__ import annotations
import hashlib
import hmac
import re
from uuid import UUID

KEY_RE = re.compile(r'^[a-zA-Z0-9_-]{16,96}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')

class ReceiptKey:
    def __init__(self, secret: bytes):
        if not isinstance(secret,bytes) or len(secret)<32 or not any(secret):
            raise ValueError('at least 32 bytes of independently generated server secret required')
        self._secret=secret

    def marker(self) -> str:
        # Durable key-epoch binding: a changed HMAC key must fail CLOSED.
        return self._hash(b'ffh-r139-key-epoch-v1\x00', b'provisioned-secret-binding')

    def user(self, uid: str) -> str:
        try:
            normalized=str(UUID(uid))
        except (ValueError,AttributeError,TypeError):
            raise ValueError('verified canonical UUID required') from None
        if uid != normalized:
            raise ValueError('canonical lowercase UUID required')
        return self._hash(b'ffh-r139-user\x00',normalized.encode())

    def receipt(self, uid: str,nonce: str) -> str:
        if not isinstance(nonce,str) or not KEY_RE.fullmatch(nonce):
            raise ValueError('bounded request ID required')
        return self._hash(b'ffh-r139-receipt\x00',bytes.fromhex(self.user(uid))+b'\x00'+nonce.encode())

    def payload(self, payload_digest: str) -> str:
        if not isinstance(payload_digest,str) or not HEX64.fullmatch(payload_digest):
            raise ValueError('broker payload SHA-256 required')
        # Even source-language/short-text digests are secret-keyed at rest.
        return self._hash(b'ffh-r139-payload\x00',bytes.fromhex(payload_digest))

    def _hash(self,domain:bytes,data:bytes)->str:
        return hmac.new(self._secret,domain+data,hashlib.sha256).hexdigest()
