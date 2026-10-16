"""Isolated PostgreSQL DB-API ledger and atomic distributed window quota.

NOT deployed / not wired to FFH production. A staging *separate write-capable*
DB credential must have only SELECT+INSERT+UPDATE on private receipt and quota
tables; no member/Auth/content writes. Server-only, TLS+role reviewed externally.
No DB driver or credentials are bundled. Requires an independently provisioned
staging database and actual concurrency tests before public deployment.

No plaintext, UUID, source, target, draft, token, or nonce reaches durable tables.
The transaction that records receipt/tombstone and reserves quota commits BEFORE
any translator call. On UNKNOWN DB commit status we fail closed; caller MUST NOT
invoke translator, because a committed receipt might already exist.
"""
from __future__ import annotations
from typing import Callable
from r136.broker import Broker, Denied
from .identity_hash import ReceiptKey

VERIFY_KEY = '''
SELECT key_fingerprint FROM ffh_broker_private.key_registry WHERE version=1
'''
INSERT_RECEIPT = '''
INSERT INTO ffh_broker_private.receipts
 (receipt_digest, user_digest, payload_digest, state)
VALUES (%s,%s,%s,'inflight')
ON CONFLICT (receipt_digest) DO NOTHING
RETURNING receipt_digest
'''
RESERVE_QUOTA = '''
INSERT INTO ffh_broker_private.quota_windows
 (user_digest,window_bucket,used_count)
VALUES (%s, floor(extract(epoch from now()) / %s)::bigint, 1)
ON CONFLICT (user_digest,window_bucket) DO UPDATE
 SET used_count=ffh_broker_private.quota_windows.used_count+1
 WHERE ffh_broker_private.quota_windows.used_count < %s
RETURNING used_count
'''
FINISH_RECEIPT = '''
UPDATE ffh_broker_private.receipts SET state=%s, finished_at=now()
 WHERE receipt_digest=%s AND state='inflight'
RETURNING state
'''

class PostgresAtomicLedger:
    """Implementation is untested on live Postgres; injected DB-API contract.

    * Atomic INSERT unique lock prevents concurrent duplicate nonce translation.
    * Atomic UPSERT gated count limits per-user requests across replicas.
    * No TTL deletion; tombstones persist. Retention must be separately reviewed.
    """
    def __init__(self, connection_factory:Callable, secret:bytes,
                 max_per_window:int=3,window_seconds:int=60):
        if not callable(connection_factory):
            raise ValueError('server-only PostgreSQL connection factory required')
        if type(max_per_window) is not int or not 1<=max_per_window<=100:
            raise ValueError('quota range 1..100')
        if type(window_seconds) is not int or not 30<=window_seconds<=3600:
            raise ValueError('window must be 30..3600 seconds')
        self._connection_factory=connection_factory
        self._key=ReceiptKey(secret)
        self._limit=max_per_window
        self._window=window_seconds

    @staticmethod
    def _cleanup(conn,cursor):
        if cursor is not None:
            try:cursor.close()
            except Exception:pass
        if conn is not None:
            try:conn.close()
            except Exception:pass

    def admission(self,owner:str,nonce:str,payload_digest:str)->None:
        receipt_id=self._key.receipt(owner,nonce)
        user_id=self._key.user(owner)
        payload_id=self._key.payload(payload_digest)
        conn=cursor=None
        try:
            conn=self._connection_factory()
            if conn is None: raise RuntimeError('database unavailable')
            # Must not rely on connection's autocommit setting or recycled tx.
            if getattr(conn,'autocommit',False):
                raise RuntimeError('transactions required for atomic admission')
            cursor=conn.cursor()
            cursor.execute(VERIFY_KEY)
            key_row=cursor.fetchone()
            import hmac
            if (not isinstance(key_row,(list,tuple)) or len(key_row)!=1 or
                not isinstance(key_row[0],str) or
                not hmac.compare_digest(key_row[0],self._key.marker())):
                raise RuntimeError('staging receipt key epoch not provisioned')
            cursor.execute(INSERT_RECEIPT,(receipt_id,user_id,payload_id))
            inserted=cursor.fetchone()
            if not inserted:
                conn.rollback()
                raise Denied(409,'request already seen; do not replay')
            cursor.execute(RESERVE_QUOTA,(user_id,self._window,self._limit))
            if not cursor.fetchone():
                conn.rollback()
                raise Denied(429,'member request quota exceeded')
            # A commit error MAY mean committed. Never call translator.
            conn.commit()
        except Denied:
            raise
        except Exception:
            if conn is not None:
                try:conn.rollback()
                except Exception:pass
            raise Denied(503,'durable admission unavailable') from None
        finally:self._cleanup(conn,cursor)

    def finish(self,owner:str,nonce:str,state:str)->None:
        if state not in ('unknown','held','done'):
            raise ValueError('invalid terminal receipt state')
        receipt_id=self._key.receipt(owner,nonce)
        conn=cursor=None
        try:
            conn=self._connection_factory()
            if conn is None or getattr(conn,'autocommit',False):
                raise RuntimeError('transactional DB required')
            cursor=conn.cursor()
            cursor.execute(VERIFY_KEY)
            key_row=cursor.fetchone()
            import hmac
            if (not isinstance(key_row,(list,tuple)) or len(key_row)!=1 or
                not isinstance(key_row[0],str) or
                not hmac.compare_digest(key_row[0],self._key.marker())):
                raise RuntimeError('staging receipt key epoch not provisioned')
            cursor.execute(FINISH_RECEIPT,(state,receipt_id))
            if not cursor.fetchone():
                conn.rollback()
                raise Denied(503,'receipt missing or already finalized')
            conn.commit()
        except Denied:raise
        except Exception:
            if conn is not None:
                try:conn.rollback()
                except Exception:pass
            # Provisional output MUST NOT be returned if receipt durability unknown.
            raise Denied(503,'receipt finalization unavailable') from None
        finally:self._cleanup(conn,cursor)

    def close(self): pass  # each operation owns its short-lived connection

class _DistributedQuotaInsideLedger:
    """Internal marker only. Quota is actually enforced in same ledger TX.

    Only constructed by make_staged_postgres_broker(), not public/user supplied.
    """
    def __init__(self,ledger:PostgresAtomicLedger):
        self.ledger=ledger
    def check(self,user_id:str)->bool:
        # Both quota + receipt committed atomically in ledger.admission().
        if not isinstance(user_id,str) or not user_id:
            return False
        return True

def make_staged_postgres_broker(verifier,classify,translate,connection_factory,
                                 secret:bytes,*,max_per_window=3,window_seconds=60):
    """Composition refuses to pair a real broker with in-memory quota/SQLite.

    This is still a staging-only adapter: requires a reviewed Auth, database
    contract and authorized staging credential not present in this packet.
    """
    ledger=PostgresAtomicLedger(connection_factory,secret,
                                max_per_window,window_seconds)
    return Broker(verifier,classify,translate,ledger,_DistributedQuotaInsideLedger(ledger))
