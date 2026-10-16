"""R149 end-to-end genuine CI GoTrue + real PostgreSQL + real Argos model.
All identities, requests and credentials are throwaway; NO cloud FFH access.
"""
import json
import os
import unittest
from r143 import ci_auth_tests as ephemeral_auth_tests
from r140.pg_ephemeral_tests import conn,SECRET,nonce
from r144.guarded_completion import make_guarded_broker
from r149.guarded_transport import GuardedLoopbackModel,ENDPOINT
from r136.broker import Denied

class RealIntegratedSynthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for env in ('FFH_R140_EPHEMERAL_ONLY','FFH_R143_EPHEMERAL_ONLY',
                    'FFH_R149_EPHEMERAL_ONLY'):
            if os.getenv(env)!='1':raise RuntimeError('CI only: '+env)
        # This creates a real signed disposable GoTrue session with current
        # terms and registered harmless non-safety English in local Postgres.
        ephemeral_auth_tests.RealAuthTest.setUpClass.__func__(cls)
        key=os.getenv('FFH_R149_MODEL_SECRET')
        if not key:raise RuntimeError('missing private loopback transport token')
        cls.model=GuardedLoopbackModel(key)
        cls.events=[]
        def probe_model(target,text):
            result=cls.model(target,text)
            cls.events.append({'status':result['status'],'target':target})
            return result
        cls.broker=make_guarded_broker(cls.online,cls.reader.source,
                                      probe_model,lambda:conn('ffh_r140_writer'),
                                      SECRET,max_per_window=3,window_seconds=60)
    def request(self,num,text=ephemeral_auth_tests.TEXT):
        return {'source':'en','target':'es','text':text,'request_id':nonce(num)}
    def state(self,num):
        from r139.identity_hash import ReceiptKey
        key=ReceiptKey(SECRET).receipt(self.uid,nonce(num))
        with conn('postgres') as db:
            return db.execute('SELECT state FROM ffh_broker_private.receipts WHERE receipt_digest=%s',(key,)).fetchone()
    def test_01_real_auth_signed_member_guarded_argos_and_durable_provisional(self):
        result=self.broker.submit(self.token,self.request(14901))
        self.assertEqual(result.get('status'),'provisional_candidate',result)
        self.assertFalse(result['human_approved'])
        self.assertEqual(result['production_writes'],0)
        self.assertTrue(isinstance(result.get('draft'),str) and len(result['draft'])>3)
        self.assertEqual(self.state(14901),('done',))
        self.assertEqual(len(self.events),1)
        print('R149_REAL_GOTRUE_POSTGRES_GUARDED_ARGOS_TRANSLATION_PASS',
            {'source_class':'synthetic_canonical','target':'es','model_status':result['status'],
              'draft_chars':len(result['draft']),'human_approved':False,
              'production_writes':0,'printed_draft':False},flush=True)
    def test_02_duplicate_never_dispatches(self):
        previous=len(self.events)
        with self.assertRaises(Denied) as e:self.broker.submit(self.token,self.request(14901))
        self.assertEqual(e.exception.status,409)
        self.assertEqual(len(self.events),previous)
        self.assertEqual(self.state(14901),('done',))
    def test_03_unregistered_text_never_dispatches(self):
        previous=len(self.events)
        with self.assertRaises(Denied) as e:
            self.broker.submit(self.token,self.request(14902,'Text not in guarded CI registry.'))
        self.assertEqual(e.exception.status,422)
        self.assertEqual(len(self.events),previous)
        self.assertIsNone(self.state(14902))
    def test_04_invalid_jwt_no_receipt_or_dispatch(self):
        previous=len(self.events)
        with self.assertRaises(Denied) as e:
            self.broker.submit(self.token[:-7]+'invalid',self.request(14903))
        self.assertIn(e.exception.status,(401,403,503))
        self.assertEqual(len(self.events),previous)
        self.assertIsNone(self.state(14903))
    def test_05_client_jwt_never_model_token(self):
        self.assertNotEqual(self.token,os.getenv('FFH_R149_MODEL_SECRET'))
        self.assertTrue(ENDPOINT.startswith('http://127.0.0.1:'))
    def test_06_real_auth_preflight_held_before_any_model_on_revocation(self):
        # Last test revokes disposable real GoTrue session; all other tests above
        # must have run first.
        previous=len(self.events)
        with conn('postgres') as db:
            db.execute('DELETE FROM auth.sessions WHERE id=%s',(self.session_id,))
        with self.assertRaises(Denied) as e:
            self.broker.submit(self.token,self.request(14904))
        self.assertIn(e.exception.status,(401,403,503))
        self.assertEqual(len(self.events),previous)
        self.assertIsNone(self.state(14904))
if __name__=='__main__':unittest.main(verbosity=2)
