"""R141 direct PostgreSQL proof of BYTE-IDENTICAL R139 ledger and R136 broker.

Runs only against disposable GitHub Actions postgres:16; never against
a Supabase project or a real user. No durable production writes.
"""
from __future__ import annotations
import concurrent.futures
import os
import subprocess
import sys
import unittest

from r136.broker import Denied, User, Verdict
from r139.postgres_ledger import PostgresAtomicLedger, make_staged_postgres_broker
from r139.identity_hash import ReceiptKey
from r140.pg_ephemeral_tests import conn, OWNER, OTHER, SECRET, PAYLOAD, nonce

class OriginalR139RealPg(unittest.TestCase):
    def setUp(self):
        if os.getenv("FFH_R140_EPHEMERAL_ONLY")!="1":
            raise RuntimeError("NEVER run R141 on production database")
        with conn("postgres") as db:
            db.execute("TRUNCATE ffh_broker_private.receipts,ffh_broker_private.quota_windows")
        self.ledger=PostgresAtomicLedger(conn,SECRET)
    def rows(self,sql):
        with conn("postgres") as db:
            return db.execute(sql).fetchall()
    def test_01_original_key_marker_matches_database(self):
        self.assertEqual(ReceiptKey(SECRET).marker(),
                         self.rows("SELECT key_fingerprint FROM ffh_broker_private.key_registry WHERE version=1")[0][0])
    def test_02_exact_receipt_and_quota_transaction(self):
        self.ledger.admission(OWNER,nonce(1),PAYLOAD)
        self.assertEqual(self.rows("SELECT state FROM ffh_broker_private.receipts"),[('inflight',)])
        self.assertEqual(self.rows("SELECT used_count FROM ffh_broker_private.quota_windows"),[(1,)])
    def test_03_original_finalization_done(self):
        self.ledger.admission(OWNER,nonce(1),PAYLOAD)
        self.ledger.finish(OWNER,nonce(1),"done")
        self.assertEqual(self.rows("SELECT state FROM ffh_broker_private.receipts"),[('done',)])
    def test_04_original_finalization_unknown_is_permanent(self):
        self.ledger.admission(OWNER,nonce(1),PAYLOAD)
        self.ledger.finish(OWNER,nonce(1),"unknown")
        with self.assertRaises(Denied) as e:self.ledger.admission(OWNER,nonce(1),PAYLOAD)
        self.assertEqual(e.exception.status,409)
        with self.assertRaises(Denied) as e:self.ledger.finish(OWNER,nonce(1),"done")
        self.assertEqual(e.exception.status,503)
    def test_05_original_16_competing_nonces_unique(self):
        def admit(i):
            try:PostgresAtomicLedger(conn,SECRET).admission(OWNER,nonce(1),PAYLOAD);return 200
            except Denied as e:return e.status
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            results=list(pool.map(admit,range(16)))
        self.assertEqual(results.count(200),1)
        self.assertEqual(results.count(409),15)
    def test_06_original_16_competing_nonces_quota(self):
        def admit(i):
            try:PostgresAtomicLedger(conn,SECRET).admission(OWNER,nonce(i),PAYLOAD);return 200
            except Denied as e:return e.status
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            results=list(pool.map(admit,range(16)))
        self.assertEqual(results.count(200),3)
        self.assertEqual(results.count(429),13)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM ffh_broker_private.receipts"),[(3,)])
    def test_07_rejected_quota_does_not_reserve_receipt(self):
        for i in range(3):self.ledger.admission(OWNER,nonce(i),PAYLOAD)
        with self.assertRaises(Denied) as e:self.ledger.admission(OWNER,nonce(3),PAYLOAD)
        self.assertEqual(e.exception.status,429)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM ffh_broker_private.receipts"),[(3,)])
    def test_08_original_separates_users(self):
        for i in range(3):self.ledger.admission(OWNER,nonce(i),PAYLOAD)
        self.ledger.admission(OTHER,nonce(0),PAYLOAD)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM ffh_broker_private.receipts"),[(4,)])
    def test_09_hmac_protected_identifiers_only(self):
        self.ledger.admission(OWNER,nonce(1),PAYLOAD)
        raw=repr(self.rows("SELECT * FROM ffh_broker_private.receipts"))
        for sensitive in (OWNER,nonce(1),PAYLOAD):
            self.assertNotIn(sensitive,raw)
    def test_10_original_wrong_key_epoch_denied(self):
        wrong=PostgresAtomicLedger(conn,b"r141_nonproduction_wrong_epoch_fabricated_0123456789abcdef")
        with self.assertRaises(Denied) as e:wrong.admission(OWNER,nonce(1),PAYLOAD)
        self.assertEqual(e.exception.status,503)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM ffh_broker_private.receipts"),[(0,)])
    def test_11_original_fail_on_autocommit(self):
        class Auto:
            def __init__(self,raw):self.raw=raw;self.autocommit=True
            def cursor(self):return self.raw.cursor()
            def rollback(self):return self.raw.rollback()
            def close(self):return self.raw.close()
        ledger=PostgresAtomicLedger(lambda:Auto(conn()),SECRET)
        with self.assertRaises(Denied) as e:ledger.admission(OWNER,nonce(1),PAYLOAD)
        self.assertEqual(e.exception.status,503)
    def test_12_commit_ack_lost_tombstone(self):
        class LostAck:
            def __init__(self,raw):self.raw=raw;self.autocommit=raw.autocommit
            def cursor(self):return self.raw.cursor()
            def commit(self):
                self.raw.commit()
                raise OSError("fabricated lost commit confirmation")
            def rollback(self):return self.raw.rollback()
            def close(self):return self.raw.close()
        with self.assertRaises(Denied) as e:
            PostgresAtomicLedger(lambda:LostAck(conn()),SECRET).admission(OWNER,nonce(1),PAYLOAD)
        self.assertEqual(e.exception.status,503)
        self.assertEqual(self.rows("SELECT count(*) FROM ffh_broker_private.receipts"),[(1,)])
        with self.assertRaises(Denied) as e:self.ledger.admission(OWNER,nonce(1),PAYLOAD)
        self.assertEqual(e.exception.status,409)
    def test_13_original_child_process_crash_after_commit(self):
        source=("from r139.postgres_ledger import PostgresAtomicLedger;"
                "from r140.pg_ephemeral_tests import conn,nonce,OWNER,SECRET,PAYLOAD;"
                "import os;"
                "PostgresAtomicLedger(conn,SECRET).admission(OWNER,nonce(21),PAYLOAD);"
                "os._exit(28)")
        run=subprocess.run([sys.executable,"-c",source],env=os.environ.copy(),
                           capture_output=True,timeout=15)
        self.assertEqual(run.returncode,28,repr(run.stderr))
        with self.assertRaises(Denied) as e:self.ledger.admission(OWNER,nonce(21),PAYLOAD)
        self.assertEqual(e.exception.status,409)
    def test_14_no_reviewed_state(self):
        self.ledger.admission(OWNER,nonce(1),PAYLOAD)
        with self.assertRaises(ValueError):self.ledger.finish(OWNER,nonce(1),"reviewed")
    def test_15_broker_does_not_dispatch_after_duplicate(self):
        hits=[]
        broker=make_staged_postgres_broker(
            lambda t:User(OWNER,"Member"),
            lambda text:Verdict(True),
            lambda target,text:(hits.append(target) or {"status":"held","human_approved":False,"production_writes":0}),
            conn,SECRET)
        req={"source":"en","target":"ko","text":"Example test-only sentence","request_id":nonce(1)}
        first=broker.submit("synthetic-bearer",req)
        self.assertEqual(first["status"],"held")
        with self.assertRaises(Denied) as e:broker.submit("synthetic-bearer",req)
        self.assertEqual(e.exception.status,409)
        self.assertEqual(len(hits),1)
    def test_16_broker_quota_before_fourth_translation(self):
        hits=[]
        broker=make_staged_postgres_broker(
            lambda t:User(OWNER,"Member"),
            lambda text:Verdict(True),
            lambda target,text:(hits.append(target) or {"status":"held","human_approved":False,"production_writes":0}),
            conn,SECRET)
        for i in range(3):
            broker.submit("synthetic-bearer",{"source":"en","target":"ja",
                "text":"Example test-only sentence","request_id":nonce(i)})
        with self.assertRaises(Denied) as e:
            broker.submit("synthetic-bearer",{"source":"en","target":"ja",
                "text":"Example test-only sentence","request_id":nonce(3)})
        self.assertEqual(e.exception.status,429)
        self.assertEqual(len(hits),3)
    def test_17_broker_rejects_protected_source_before_write(self):
        hits=[]
        broker=make_staged_postgres_broker(
            lambda t:User(OWNER,"Member"),lambda text:Verdict(False,"safety"),
            lambda target,text:hits.append(target),conn,SECRET)
        with self.assertRaises(Denied) as e:
            broker.submit("synthetic-bearer",{"source":"en","target":"ja",
                "text":"Fabricated safety source","request_id":nonce(1)})
        self.assertEqual(e.exception.status,422)
        self.assertEqual(hits,[])
        self.assertEqual(self.rows("SELECT count(*) FROM ffh_broker_private.receipts"),[(0,)])
    def test_18_broker_rejects_unknown_identity_before_write(self):
        broker=make_staged_postgres_broker(lambda t:None,lambda x:Verdict(True),
                 lambda target,text:{},conn,SECRET)
        with self.assertRaises(Denied) as e:
            broker.submit("synthetic-bearer",{"source":"en","target":"fr",
                "text":"Invented source","request_id":nonce(1)})
        self.assertEqual(e.exception.status,401)
        self.assertEqual(self.rows("SELECT count(*) FROM ffh_broker_private.receipts"),[(0,)])
    def test_19_broker_returns_provisional_only(self):
        broker=make_staged_postgres_broker(lambda t:User(OWNER,"Member"),lambda x:Verdict(True),
            lambda target,text:{"status":"provisional_candidate","draft":"Test draft",
                    "human_approved":False,"production_writes":0},conn,SECRET)
        response=broker.submit("synthetic-bearer",{"source":"en","target":"de",
            "text":"Fabricated benign source","request_id":nonce(1)})
        self.assertEqual(response["status"],"provisional_candidate")
        self.assertFalse(response["human_approved"])
        self.assertEqual(response["production_writes"],0)
        self.assertEqual(self.rows("SELECT state FROM ffh_broker_private.receipts"),[("done",)])
    def test_20_broker_translator_failure_becomes_unknown_no_replay(self):
        called=[]
        def crashed(target,text):
            called.append(1)
            raise OSError("fabricated backend disconnect")
        broker=make_staged_postgres_broker(lambda t:User(OWNER,"Member"),
            lambda x:Verdict(True),crashed,conn,SECRET)
        request={"source":"en","target":"vi","text":"Invented harmless string","request_id":nonce(1)}
        with self.assertRaises(Denied) as e:broker.submit("synthetic-bearer",request)
        self.assertEqual(e.exception.status,502)
        with self.assertRaises(Denied) as e:broker.submit("synthetic-bearer",request)
        self.assertEqual(e.exception.status,409)
        self.assertEqual(len(called),1)
    def test_21_writer_cannot_select_raw_payload_hash(self):
        self.ledger.admission(OWNER,nonce(1),PAYLOAD)
        with conn() as db, self.assertRaises(Exception):
            db.execute("SELECT payload_digest FROM ffh_broker_private.receipts")
    def test_22_writer_cannot_delete_receipt(self):
        self.ledger.admission(OWNER,nonce(1),PAYLOAD)
        with conn() as db, self.assertRaises(Exception):
            db.execute("DELETE FROM ffh_broker_private.receipts")
    def test_23_original_key_digest_compatible_with_reference(self):
        from r140.pg_real import Key
        key=ReceiptKey(SECRET);previous=Key(SECRET)
        self.assertEqual(key.user(OWNER),previous.user(OWNER))
        self.assertEqual(key.receipt(OWNER,nonce(1)),previous.receipt(OWNER,nonce(1)))
        self.assertEqual(key.payload(PAYLOAD),previous.payload(PAYLOAD))
        self.assertEqual(key.marker(),previous.marker())
