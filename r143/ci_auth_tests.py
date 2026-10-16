"""Disposable self-hosted GoTrue Auth plus R139 ledger and R142 source rules."""
import json
import os
import urllib.request
import urllib.error
import unittest
from r140.pg_ephemeral_tests import conn,SECRET,nonce
from r139.postgres_ledger import make_staged_postgres_broker
from r143.private_auth import PrivateMemberReadOnly
from r143.online_auth import OnlineAuth,decode_untrusted_session
from r136.broker import Denied

URL="http://127.0.0.1:9999"
TEXT="Diced vegetables in a clean container."
SRC="e"*64

def auth(method,path,body=None,token=None):
    headers={"Content-Type":"application/json"}
    if token:headers["Authorization"]="Bearer "+token
    data=json.dumps(body).encode() if body is not None else None
    request=urllib.request.Request(URL+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(request,timeout=6) as response:
            return response.status,json.loads(response.read())
    except urllib.error.HTTPError as error:
        error.read();return error.code,{}

class RealAuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv("FFH_R143_EPHEMERAL_ONLY")!="1":
            raise RuntimeError("disposable CI only")
        cls.reader=PrivateMemberReadOnly(lambda:conn("ffh_r140_reader"))
        cls.online=OnlineAuth(URL+"/user",cls.reader,local_ci=True)
        email="r143-local@example.test"
        password="local-only-NotARealCredential_1234"
        signup,_=auth("POST","/signup",{"email":email,"password":password})
        if signup not in (200,201):raise RuntimeError("isolated signup "+str(signup))
        status,result=auth("POST","/token?grant_type=password",{"email":email,"password":password})
        if status!=200:raise RuntimeError("isolated login "+str(status))
        cls.token=result["access_token"]
        cls.uid=result["user"]["id"]
        cls.session_id=decode_untrusted_session(cls.token)
        with conn("postgres") as db:
            db.execute("INSERT INTO public.ffh_member_profiles(user_id) VALUES (%s)",(cls.uid,))
            db.execute("INSERT INTO public.ffh_terms_acceptances(user_id,terms_version) VALUES (%s,'2026-09-17-v1')",(cls.uid,))
            db.execute("INSERT INTO public.ffh_translation_memory(source_hash,source_text,source_class,is_safety_critical) VALUES (%s,%s,'ui',false)",(SRC,TEXT))
            db.execute("INSERT INTO public.ffh_translation_accuracy_review(source_hash,translation_gate) VALUES (%s,'normal')",(SRC,))
    def make_broker(self,events):
        return make_staged_postgres_broker(self.online,self.reader.source,
            lambda lang,text:(events.append(lang) or {"status":"held","human_approved":False,"production_writes":0}),
            lambda:conn("ffh_r140_writer"),SECRET)
    def request(self,n):
        return {"source":"en","target":"es","text":TEXT,"request_id":nonce(n)}
    def test_00_eligibility_boolean_diagnostics(self):
        with conn("postgres") as db:
            row=db.execute("""SELECT email_confirmed_at IS NOT NULL,
                        COALESCE(is_anonymous,false),deleted_at IS NULL,
                        banned_until IS NULL
                        FROM auth.users WHERE id=%s""",(self.uid,)).fetchone()
            sessions=db.execute("SELECT COUNT(*) FROM auth.sessions WHERE id=%s AND user_id=%s",
                               (self.session_id,self.uid)).fetchone()[0]
            profile=db.execute("SELECT COUNT(*) FROM public.ffh_member_profiles WHERE user_id=%s",
                              (self.uid,)).fetchone()[0]
            terms=db.execute("SELECT COUNT(*) FROM public.ffh_terms_acceptances WHERE user_id=%s",
                            (self.uid,)).fetchone()[0]
        with conn("ffh_r140_reader") as read_db:
            try:
                read_db.execute("SELECT id FROM auth.users LIMIT 1")
            except Exception:
                print("R143_DIRECT_AUTH_SELECT_DENIED_EXPECTED",flush=True)
            else:
                raise AssertionError("Direct auth.users SELECT unexpectedly allowed")
        print("R143_AUTH_BOOLEAN_DIAG",
              {"user_row_flags":row,"session_match":sessions,
               "has_profile":profile,"terms_count":terms,
               "verified_member":self.reader.member(self.uid,self.session_id) is not None,
               "online_member":self.online(self.token) is not None},
              flush=True)
        self.assertEqual(sessions,1)
    def test_01_genuine_token_and_membership(self):
        status,data=auth("GET","/user",token=self.token)
        self.assertEqual(status,200)
        self.assertEqual(data["id"],self.uid)
        self.assertEqual(self.online(self.token).role,"Member")
    def test_02_real_signed_token_broker_and_receipts(self):
        calls=[];broker=self.make_broker(calls)
        self.assertEqual(broker.submit(self.token,self.request(0))["status"],"held")
        with self.assertRaises(Denied) as err:broker.submit(self.token,self.request(0))
        self.assertEqual(err.exception.status,409)
        self.assertEqual(calls,["es"])
    def test_03_invalid_token_denied_before_dispatch(self):
        calls=[];broker=self.make_broker(calls)
        with self.assertRaises(Denied):
            broker.submit(self.token[:-5]+"xxxxx",self.request(1))
        self.assertEqual(calls,[])
    def test_04_nonregistered_text_denied_before_dispatch(self):
        calls=[];broker=self.make_broker(calls)
        with self.assertRaises(Denied) as err:
            broker.submit(self.token,{**self.request(2),"text":"Not registered as canonical English"})
        self.assertEqual(err.exception.status,422)
        self.assertEqual(calls,[])
    def test_05_revoked_session_denied(self):
        with conn("postgres") as db:
            db.execute("DELETE FROM auth.sessions WHERE id=%s",(self.session_id,))
        self.assertIsNone(self.online(self.token))
