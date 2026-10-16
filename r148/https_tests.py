"""R148 public-hosted negative JWT tests plus page/no-approval security assertions."""
import pathlib,re,subprocess,unittest,urllib.request,urllib.error,json,tempfile
BASE='https://hlsjzjnondimwhqbgjqm.supabase.co'
class R148AdmitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index=pathlib.Path('docs/index.html').read_text('utf-8')
        cls.js=pathlib.Path('docs/r148.js').read_text('utf-8')
        cls.ddl=pathlib.Path('r148/01_private_staging_receipts.sql').read_text('utf-8')
        cls.rpc=pathlib.Path('r148/02_authenticated_stage_admission.sql').read_text('utf-8')
        m=re.search(r'const PUB="(sb_publishable_[A-Za-z0-9_-]+)"',cls.index)
        if not m:raise AssertionError('staging publishable key unavailable')
        cls.pub=m.group(1)
    def test_01_second_script_attached(self):
        self.assertIn('<script src="./r148.js"></script>',self.index)
    def test_02_staging_buttons_default_disabled(self):
        self.assertIn('id="stage" disabled',self.index)
        self.assertIn('id="duplicate" disabled',self.index)
        self.assertIn("el('stage').disabled=false",self.index)
    def test_03_isolated_script_parses_in_node(self):
        with tempfile.TemporaryDirectory() as folder:
            f=pathlib.Path(folder,'r148.js');f.write_text(self.js,'utf8')
            p=subprocess.run(['node','--check',str(f)],capture_output=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr.decode()[:300])
    def test_04_no_storage_or_model_calls(self):
        for text in ('localStorage','sessionStorage','document.cookie',
                     '/translate','/guarded-translate','service_role','sb_secret_'):
            self.assertNotIn(text,self.js)
    def test_05_positive_staging_is_only_held(self):
        self.assertIn("data.status==='staging_held'",self.js)
        self.assertIn('data.model_connected!==false',self.js)
        self.assertIn('data.production_writes===0',self.js)
    def test_06_real_session_rechecked(self):
        self.assertIn("BASE+'/auth/v1/user'",self.js)
        self.assertIn("Authorization:'Bearer '+token",self.js)
    def test_07_request_nonce_cryptographic(self):
        self.assertIn('crypto.getRandomValues(new Uint8Array(16))',self.js)
    def test_08_duplicate_never_replays(self):
        self.assertIn("data.status==='duplicate'",self.js)
        self.assertIn('p_nonce:nonce',self.js)
    def test_09_backend_binds_real_member_session(self):
        self.assertIn('v_uid := auth.uid();',self.rpc)
        self.assertIn("v_session_str := auth.jwt()->>'session_id';",self.rpc)
        self.assertIn('ffh_r146_sandbox.member_status',self.rpc)
    def test_10_private_hmac_and_atomic_on_conflict(self):
        self.assertIn('extensions.hmac',self.rpc)
        self.assertIn('ON CONFLICT(receipt_digest) DO NOTHING',self.rpc)
        self.assertIn('EXCEPTION WHEN SQLSTATE',self.rpc)
        self.assertIn('used_count<3',self.rpc)
    def test_11_not_translating_or_publishing_sql(self):
        self.assertIn("'status','staging_held'",self.rpc)
        self.assertIn("'model_connected',false",self.rpc)
        self.assertIn("'production_writes',0",self.rpc)
    def test_12_anonymous_execute_revoke(self):
        self.assertIn('FROM PUBLIC,anon,authenticated',self.rpc)
        self.assertIn(' TO authenticated',self.rpc)
    def test_13_private_rls_force(self):
        self.assertEqual(self.ddl.count('FORCE ROW LEVEL SECURITY'),3)
    @staticmethod
    def request(authorization=None):
        headers={'apikey':R148AdmitTests.pub,'Content-Type':'application/json'}
        if authorization:headers['Authorization']='Bearer '+authorization
        b=json.dumps({'p_source':'FFH R146 interface label for staging verification.',
            'p_target':'ja','p_nonce':'R148_unit_negative_1234567890'}).encode()
        req=urllib.request.Request(BASE+'/rest/v1/rpc/ffh_r148_stage_admit',
            data=b,method='POST',headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=12) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code
    def test_14_no_bearer_denied_hosted(self):
        self.assertIn(self.request(),(401,403))
    def test_15_forged_bearer_denied_hosted(self):
        self.assertIn(self.request('not.a.validJWT'),(401,403))
    def test_16_client_cannot_read_private_receipts(self):
        req=urllib.request.Request(BASE+'/rest/v1/r148_receipts?select=receipt_digest&limit=1',
             headers={'apikey':self.pub,'Accept-Profile':'ffh_r146_sandbox'})
        try:
            with urllib.request.urlopen(req,timeout=12) as resp:code=resp.status
        except urllib.error.HTTPError as e:code=e.code
        self.assertEqual(code,406)
if __name__=='__main__':unittest.main(verbosity=2)
