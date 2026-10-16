"""R143 server-side online Supabase Auth /user adapter. Staging/CI only.

Online Auth validates the presented JWT, NOT a client-provided UID or role.
Decode only the untrusted session_id claim after successful online /user;
a *separate read-only server DB query* requires session_id AND signed-in uid
to match auth.sessions, preventing revoked-session reuse. Do not persist bearer
tokens or personal email addresses.

Do NOT use on production until HTTPS trust, egress pinning, connection pooling,
real Supabase Auth integration, security review, rate limits, and independent
secrets are verified. This module cannot grant roles or write any records.
"""
from __future__ import annotations
import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID
from r142.schema_matched import RegisteredReadOnly

MAX_JWT_BYTES=8192
class AuthUnavailable(Exception):pass

def decode_untrusted_session(token:str)->str:
    """Untrusted JWT claim used ONLY as a selector in independently validated DB."""
    if type(token)!=str or len(token)<30 or len(token)>MAX_JWT_BYTES:
        raise ValueError("bad bearer length")
    chunks=token.split(".")
    if len(chunks)!=3 or any(not p or re.fullmatch(r"[A-Za-z0-9_-]+",p) is None for p in chunks):
        raise ValueError("malformed JWT")
    if len(chunks[1])>4096:raise ValueError("oversized JWT payload")
    pad="="*((-len(chunks[1]))%4)
    decoded=base64.urlsafe_b64decode(chunks[1]+pad)
    if len(decoded)>3072:raise ValueError("oversized JWT claims")
    payload=json.loads(decoded)
    if type(payload)!=dict:raise ValueError("invalid JWT claim object")
    session_id=payload.get("session_id")
    if type(session_id)!=str or str(UUID(session_id))!=session_id:
        raise ValueError("verified token missing canonical session ID")
    return session_id

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise AuthUnavailable("auth redirect forbidden")

class OnlineAuth:
    def __init__(self,endpoint:str,reader:RegisteredReadOnly,*,local_ci=False,timeout=3):
        if type(endpoint)!=str or endpoint.count("?") or endpoint.count("#"):
            raise ValueError("fixed server Auth user URL required")
        parsed=urllib.parse.urlsplit(endpoint)
        if parsed.username or parsed.password or parsed.fragment or parsed.query or not parsed.hostname:
            raise ValueError("unsafe URL")
        is_loopback=parsed.hostname in ("127.0.0.1","localhost") and parsed.scheme=="http"
        if not ((parsed.scheme=="https" and parsed.path.endswith("/auth/v1/user")) or
                (local_ci and is_loopback and parsed.path=="/user")):
            raise ValueError("HTTPS hosted /auth/v1/user or explicit loopback CI only")
        if local_ci and not is_loopback:
            raise ValueError("CI bypass requires local address")
        if type(timeout) not in (int,float) or timeout<=0 or timeout>5:
            raise ValueError("bounded auth timeout")
        self.endpoint=endpoint;self.reader=reader;self.timeout=timeout
        self.opener=urllib.request.build_opener(NoRedirect())
    def __call__(self,token:str):
        if type(token)!=str or not 30<=len(token)<=MAX_JWT_BYTES:
            return None
        try:
            session_id=decode_untrusted_session(token)
        except Exception:
            return None
        req=urllib.request.Request(self.endpoint,
                 headers={"Authorization":"Bearer "+token,
                          "Accept":"application/json"},
                 method="GET")
        try:
            with self.opener.open(req,timeout=self.timeout) as response:
                if response.status!=200:return None
                if (response.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                    raise AuthUnavailable("invalid Auth content type")
                data=response.read(16385)
                if len(data)>16384:raise AuthUnavailable("oversized Auth response")
                result=json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code in (400,401,403):
                e.close()
                return None
            e.close()
            raise AuthUnavailable("Auth HTTP service unavailable") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,AuthUnavailable):
            raise AuthUnavailable("Auth lookup failed closed") from None
        if type(result)!=dict:raise AuthUnavailable("unexpected Auth body")
        # GoTrue /user returns user object itself; never trust JWT user_metadata.
        user_id=result.get("id")
        if type(user_id)!=str:return None
        try:
            if str(UUID(user_id))!=user_id:return None
        except (ValueError,TypeError,AttributeError):return None
        if result.get("is_anonymous") is True:return None
        # R142 DB reader verifies user-id, row status, terms, and **existing**
        # session_id. A forged or revoked session selector cannot pass DB checks.
        return self.reader.member(user_id,session_id)
