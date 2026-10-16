"""FFH R140 disposable real PostgreSQL 16 integration; NO production secrets."""
from __future__ import annotations
import hashlib,hmac,os,re
from uuid import UUID
SECRET=b'R140_ephemeral_test_secret_only_00000000000000000000'
OWNER='00000000-0000-4000-8000-000000000001'
OTHER='00000000-0000-4000-8000-000000000002'
PAYLOAD='a'*64
VERIFY_KEY='SELECT key_fingerprint FROM ffh_broker_private.key_registry WHERE version=1'
INSERT_RECEIPT="""INSERT INTO ffh_broker_private.receipts
(receipt_digest,user_digest,payload_digest,state)
VALUES (%s,%s,%s,'inflight')
ON CONFLICT (receipt_digest) DO NOTHING RETURNING receipt_digest"""
RESERVE_QUOTA="""INSERT INTO ffh_broker_private.quota_windows
(user_digest,window_bucket,used_count)
VALUES (%s,floor(extract(epoch from now()) / %s)::bigint,1)
ON CONFLICT (user_digest,window_bucket) DO UPDATE
SET used_count=ffh_broker_private.quota_windows.used_count+1
WHERE ffh_broker_private.quota_windows.used_count < %s
RETURNING used_count"""
FINISH_RECEIPT="""UPDATE ffh_broker_private.receipts SET state=%s,finished_at=now()
WHERE receipt_digest=%s AND state='inflight' RETURNING state"""
class Denied(Exception):
    def __init__(self,status,reason):
        super().__init__(reason);self.status=status
class Key:
    def __init__(self,secret):
        if not isinstance(secret,bytes) or len(secret)<32:raise ValueError('secret')
        self.secret=secret
    def digest(self,domain,body):
        return hmac.new(self.secret,domain+body,hashlib.sha256).hexdigest()
    def marker(self):
        return self.digest(b'ffh-r139-key-epoch-v1\x00',b'provisioned-secret-binding')
    def user(self,uid):
        if str(UUID(uid))!=uid:raise ValueError('canonical UUID')
        return self.digest(b'ffh-r139-user\x00',uid.encode())
    def receipt(self,uid,nonce):
        if not isinstance(nonce,str) or re.fullmatch('[a-zA-Z0-9_-]{16,96}',nonce) is None:
            raise ValueError('nonce')
        return self.digest(b'ffh-r139-receipt\x00',
                           bytes.fromhex(self.user(uid))+b'\x00'+nonce.encode())
    def payload(self,value):
        if re.fullmatch('[0-9a-f]{64}',value) is None:raise ValueError('sha256')
        return self.digest(b'ffh-r139-payload\x00',bytes.fromhex(value))
class Ledger:
    def __init__(self,connection_factory,secret=SECRET,cap=3,window=60):
        if os.getenv('FFH_R140_EPHEMERAL_ONLY')!='1':
            raise RuntimeError('R140 isolated CI only')
        if type(cap)!=int or not 1<=cap<=100 or type(window)!=int or not 30<=window<=3600:
            raise ValueError('quota')
        self.connect=connection_factory;self.key=Key(secret);self.cap=cap;self.window=window
    def _check(self,c):
        c.execute(VERIFY_KEY);row=c.fetchone()
        if not row or not hmac.compare_digest(row[0],self.key.marker()):
            raise RuntimeError('receipt key epoch mismatch')
    def admission(self,uid,nonce,payload=PAYLOAD):
        receipt=self.key.receipt(uid,nonce);user=self.key.user(uid)
        payload_hash=self.key.payload(payload);conn=None
        try:
            conn=self.connect()
            if conn.autocommit:raise RuntimeError('no autocommit')
            with conn.cursor() as c:
                self._check(c)
                c.execute(INSERT_RECEIPT,(receipt,user,payload_hash))
                if not c.fetchone():
                    conn.rollback();raise Denied(409,'duplicate')
                c.execute(RESERVE_QUOTA,(user,self.window,self.cap))
                if not c.fetchone():
                    conn.rollback();raise Denied(429,'quota')
                conn.commit()
        except Denied:raise
        except Exception:
            if conn:
                try:conn.rollback()
                except Exception:pass
            raise Denied(503,'durable admission uncertain') from None
        finally:
            if conn:conn.close()
    def finish(self,uid,nonce,state):
        if state not in ('done','held','unknown'):raise ValueError('bad state')
        conn=None
        try:
            conn=self.connect()
            if conn.autocommit:raise RuntimeError('no autocommit')
            with conn.cursor() as c:
                self._check(c)
                c.execute(FINISH_RECEIPT,(state,self.key.receipt(uid,nonce)))
                if not c.fetchone():
                    conn.rollback();raise Denied(503,'already finalized')
                conn.commit()
        except Denied:raise
        except Exception:
            if conn:
                try:conn.rollback()
                except Exception:pass
            raise Denied(503,'durable finalization uncertain') from None
        finally:
            if conn:conn.close()
