"""R145 deferred finish contract: failed final checks must never record DONE."""
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from r136.broker import Broker,Denied,User,Verdict,MemoryQuota
from r144.guarded_completion import GuardedBroker
OWNER="00000000-0000-4000-8000-000000000001"
OTHER="00000000-0000-4000-8000-000000000002"
REQ={"source":"en","target":"fr","text":"Clean chopped vegetables.",
     "request_id":"r145_unique_request_id_0001"}
DRAFT={"status":"provisional_candidate","draft":"Fake only",
       "human_approved":False,"production_writes":0}
class Ledger:
    def __init__(self):
        self.rows={};self.lock=threading.RLock();self.fail_on=None
    def admission(self,uid,nonce,payload):
        with self.lock:
            if (uid,nonce) in self.rows:raise Denied(409,"duplicate")
            self.rows[uid,nonce]="inflight"
    def finish(self,uid,nonce,state):
        with self.lock:
            if self.fail_on==state:raise Denied(503,"commit ambiguous")
            if self.rows.get((uid,nonce))!="inflight":raise Denied(503,"not inflight")
            self.rows[uid,nonce]=state
class Finalization(unittest.TestCase):
    def setUp(self):
        self.ledger=Ledger();self.nv=0;self.ns=0
        self.verify_out=lambda n:User(OWNER,"Member")
        self.source_out=lambda n:Verdict(True)
        self.model=lambda target,text:dict(DRAFT)
        self.guard=self.make()
    def verify(self,token):
        self.nv+=1;return self.verify_out(self.nv)
    def source(self,text):
        self.ns+=1;return self.source_out(self.ns)
    def translate(self,target,text):
        if not self.source(text).allowed:return {"status":"held"}
        result=self.model(target,text)
        if not self.source(text).allowed:return {"status":"held"}
        return result
    def make(self):
        core=Broker(self.verify,self.source,self.translate,self.ledger,MemoryQuota(20,60))
        return GuardedBroker(core,self.verify,self.source)
    def state(self):return self.ledger.rows.get((OWNER,REQ["request_id"]))
    def submit(self):return self.guard.submit("fake-token",REQ)
    def test_01_valid_release_done(self):
        self.assertEqual(self.submit()["status"],"provisional_candidate")
        self.assertEqual(self.state(),"done")
    def test_02_mid_inference_source_hold(self):
        self.source_out=lambda n:Verdict(n<3)
        with self.assertRaises(Denied):self.submit()
        self.assertEqual(self.state(),"held")
    def test_03_last_source_hold(self):
        self.source_out=lambda n:Verdict(n<4)
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,422);self.assertEqual(self.state(),"held")
    def test_04_final_suspension_hold(self):
        self.verify_out=lambda n:User(OWNER,"Member",n<2)
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,403);self.assertEqual(self.state(),"held")
    def test_05_final_different_identity_hold(self):
        self.verify_out=lambda n:User(OWNER if n<2 else OTHER,"Member")
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,403);self.assertEqual(self.state(),"held")
    def test_06_online_auth_unavailable_hold(self):
        def change(n):
            if n>1:raise OSError("offline")
            return User(OWNER,"Member")
        self.verify_out=change
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,503);self.assertEqual(self.state(),"held")
    def test_07_source_registry_unavailable_hold(self):
        def change(n):
            if n>=4:raise OSError("offline")
            return Verdict(True)
        self.source_out=change
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,503);self.assertEqual(self.state(),"held")
    def test_08_uncertain_done_commit_holds_response(self):
        self.ledger.fail_on="done"
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,503);self.assertEqual(self.state(),"inflight")
    def test_09_uncertain_held_commit_holds_response(self):
        self.ledger.fail_on="held"
        self.verify_out=lambda n:User(OWNER,"Member",n<2)
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,503);self.assertEqual(self.state(),"inflight")
    def test_10_process_crash_remains_nonreplayable(self):
        def abort(n):
            if n>1:raise SystemExit(7)
            return User(OWNER,"Member")
        self.verify_out=abort
        with self.assertRaises(SystemExit):self.submit()
        self.assertEqual(self.state(),"inflight")
        self.verify_out=lambda n:User(OWNER,"Member")
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,409);self.assertEqual(self.state(),"inflight")
    def test_11_held_is_not_replayable(self):
        self.verify_out=lambda n:User(OWNER,"Member",n<2)
        with self.assertRaises(Denied):self.submit()
        self.verify_out=lambda n:User(OWNER,"Member")
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,409);self.assertEqual(self.state(),"held")
    def test_12_parallel_requests_no_cross_account_state(self):
        def one(i):
            q={**REQ,"request_id":REQ["request_id"]+str(i)}
            return self.guard.submit("fake-token",q)["status"]
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(one,range(8))),["provisional_candidate"]*8)
        self.assertEqual(list(self.ledger.rows.values()).count("done"),8)
    def test_13_model_held_state(self):
        self.model=lambda t,x:{"status":"held","human_approved":False,"production_writes":0}
        self.assertEqual(self.submit()["status"],"held")
        self.assertEqual(self.state(),"held")
    def test_14_auto_approval_stays_unknown(self):
        self.model=lambda t,x:{"status":"provisional_candidate","draft":"test",
            "human_approved":True,"production_writes":1}
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,502);self.assertEqual(self.state(),"unknown")
    def test_15_initial_token_bad_no_receipt(self):
        self.verify_out=lambda n:None
        with self.assertRaises(Denied) as e:self.submit()
        self.assertEqual(e.exception.status,401);self.assertEqual(self.ledger.rows,{})
