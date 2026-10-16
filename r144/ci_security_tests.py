"""Genuine GoTrue signed tokens + real PostgreSQL post-inference safety race tests.

Disposable CI only. No real FFH members, models, content, or database writes.
"""
import unittest
from r143.ci_auth_tests import auth,URL as ROOT,TEXT,SRC,TERMS
from r143.online_auth import OnlineAuth,decode_untrusted_session
from r143.private_auth import PrivateMemberReadOnly
from r144.guarded_completion import make_guarded_broker
from r140.pg_ephemeral_tests import conn,SECRET,nonce
from r136.broker import Denied

EMAIL="r144-local@example.test"
PASSWORD="R144-Dummy-Local-Login-Only_42"

class RevalidationCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        status,_=auth("POST","/signup",{"email":EMAIL,"password":PASSWORD})
        if status not in (200,201):raise RuntimeError("R144 isolated signup rejected "+str(status))
        status,out=auth("POST","/token?grant_type=password",{"email":EMAIL,"password":PASSWORD})
        if status!=200:raise RuntimeError("R144 isolated Auth token not issued")
        cls.token=out["access_token"];cls.uid=out["user"]["id"]
        cls.sid=decode_untrusted_session(cls.token)
        cls.reader=PrivateMemberReadOnly(lambda:conn("ffh_r140_reader"))
        cls.online=OnlineAuth(ROOT+"/user",cls.reader,local_ci=True)
        with conn("postgres") as db:
            db.execute("INSERT INTO public.ffh_member_profiles VALUES (%s)",(cls.uid,))
            db.execute("INSERT INTO public.ffh_terms_acceptances VALUES (%s,%s)",(cls.uid,TERMS))
    @classmethod
    def tearDownClass(cls):cls.token=None
    def setUp(self):
        with conn("postgres") as db:
            db.execute("TRUNCATE ffh_broker_private.receipts,ffh_broker_private.quota_windows")
            db.execute("DELETE FROM public.ffh_translation_protected_source_overrides")
            db.execute("DELETE FROM public.ffh_terms_acceptances WHERE user_id=%s",(self.uid,))
            db.execute("INSERT INTO public.ffh_terms_acceptances VALUES (%s,%s)",(self.uid,TERMS))
            db.execute("UPDATE auth.users SET banned_until=NULL WHERE id=%s",(self.uid,))
        self.hit=[]
    def broker(self,translate):
        return make_guarded_broker(self.online,self.reader.source,translate,
                                   lambda:conn("ffh_r140_writer"),SECRET)
    def request(self,n=0):
        return {"source":"en","target":"fr","text":TEXT,"request_id":nonce(n)}
    def draft(self,target,text):
        self.hit.append(target)
        return {"status":"provisional_candidate","draft":"Fabricated model candidate",
                "human_approved":False,"production_writes":0}
    def states(self):
        with conn("postgres") as db:
            return db.execute("SELECT state FROM ffh_broker_private.receipts").fetchall()
    def test_01_real_token_happy_path(self):
        result=self.broker(self.draft).submit(self.token,self.request())
        self.assertEqual(result["status"],"provisional_candidate")
        self.assertFalse(result["human_approved"])
        self.assertEqual(self.states(),[("done",)])
    def test_02_source_protected_during_inference_withheld(self):
        def protect(target,text):
            self.hit.append("model_called")
            with conn("postgres") as db:
                db.execute("INSERT INTO public.ffh_translation_protected_source_overrides VALUES (%s)",(SRC,))
            return self.draft(target,text)
        with self.assertRaises(Denied) as e:self.broker(protect).submit(self.token,self.request())
        self.assertEqual(e.exception.status,422)
        self.assertEqual(self.states(),[("held",)])
    def test_03_source_protected_before_dispatch_never_calls_model(self):
        with conn("postgres") as db:
            db.execute("INSERT INTO public.ffh_translation_protected_source_overrides VALUES (%s)",(SRC,))
        with self.assertRaises(Denied) as e:self.broker(self.draft).submit(self.token,self.request())
        self.assertEqual(e.exception.status,422)
        self.assertEqual(self.hit,[])
        self.assertEqual(self.states(),[])
    def test_04_account_suspended_during_translation_withheld(self):
        def suspend(target,text):
            with conn("postgres") as db:
                db.execute("UPDATE auth.users SET banned_until=now()+interval '1 day' WHERE id=%s",(self.uid,))
            return self.draft(target,text)
        with self.assertRaises(Denied) as e:self.broker(suspend).submit(self.token,self.request())
        self.assertIn(e.exception.status,(403,503))
        self.assertEqual(self.states(),[("done",)])
    def test_05_terms_revoked_during_translation_withheld(self):
        def revoke_terms(target,text):
            with conn("postgres") as db:
                db.execute("DELETE FROM public.ffh_terms_acceptances WHERE user_id=%s",(self.uid,))
            return self.draft(target,text)
        with self.assertRaises(Denied) as e:self.broker(revoke_terms).submit(self.token,self.request())
        self.assertEqual(e.exception.status,403)
        self.assertEqual(self.states(),[("done",)])
    def test_06_model_cannot_approve_automatically(self):
        def injected(target,text):
            return {"status":"provisional_candidate","draft":"sample",
                    "human_approved":True,"production_writes":1}
        with self.assertRaises(Denied) as e:self.broker(injected).submit(self.token,self.request())
        self.assertEqual(e.exception.status,502)
        self.assertEqual(self.states(),[("unknown",)])
    def test_07_backend_connection_failure_never_replayed(self):
        def crash(target,text):raise OSError("synthetic model crash")
        broker=self.broker(crash)
        with self.assertRaises(Denied) as e:broker.submit(self.token,self.request())
        self.assertEqual(e.exception.status,502)
        with self.assertRaises(Denied) as e:broker.submit(self.token,self.request())
        self.assertEqual(e.exception.status,409)
        self.assertEqual(self.states(),[("unknown",)])
    def test_08_member_remains_authorized_without_changes(self):
        self.assertEqual(self.online(self.token).role,"Member")
    def test_09_session_deleted_mid_inference_never_leaks_draft(self):
        def revoke_session(target,text):
            with conn("postgres") as db:
                db.execute("DELETE FROM auth.sessions WHERE id=%s",(self.sid,))
            return self.draft(target,text)
        with self.assertRaises(Denied) as e:self.broker(revoke_session).submit(self.token,self.request())
        self.assertIn(e.exception.status,(403,503))
        self.assertEqual(self.states(),[("done",)])
