"""R147 real HTTPS staging-only negative and browser endpoint tests.
Does NOT enroll users, send email, store tokens or dispatch translator.
"""
import os,unittest,urllib.request,urllib.error,re,subprocess,tempfile,pathlib
URL='https://hlsjzjnondimwhqbgjqm.supabase.co'
SLUG='/functions/v1/ffh-r147-member-test'
KEY=os.environ['FFH_STAGING_PUBLISHABLE_KEY']
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise RuntimeError('redirect forbidden')
def api(path,method='GET',body=None,headers=None):
    h={'Accept':'text/html,application/json','User-Agent':'FFH-R147-staging-ci'}
    if headers:h.update(headers)
    req=urllib.request.Request(URL+path,data=body,method=method,headers=h)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=12) as r:
            return r.status,{k.lower():v for k,v in r.headers.items()},r.read(250000)
    except urllib.error.HTTPError as e:
        return e.code,{k.lower():v for k,v in e.headers.items()},e.read(30000)
class LiveStage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('FFH_R147_STAGE_ONLY')!='1':raise RuntimeError('staging guard')
        if os.getenv('GITHUB_REF_NAME')!='ffh-r147-hosted-member-auth-probe-20261017':raise RuntimeError('branch guard')
        cls.status,cls.headers,cls.page=api(SLUG)
    def test_01_https_get(self):
        self.assertEqual(self.status,200)
        self.assertIn(b'FFH staging account test',self.page)
    def test_02_no_cache(self):
        self.assertIn('no-store',self.headers.get('cache-control',''))
    def test_03_browser_frame_denied(self):
        self.assertEqual(self.headers.get('x-frame-options'),'DENY')
    def test_04_csp_same_project_only(self):
        value=self.headers.get('content-security-policy','')
        self.assertIn("default-src 'none'",value)
        self.assertIn("frame-ancestors 'none'",value)
    def test_05_html_only_no_password(self):
        self.assertNotIn(b'type="password"',self.page)
        self.assertIn(b'create_user:false',self.page)
        self.assertIn(b'history.replaceState',self.page)
    def test_06_no_model_dispatch(self):
        self.assertIn(b'Model dispatch remains OFF.',self.page)
        self.assertIn(b'model_connected',self.page)
    def test_07_head_supported(self):
        st,h,d=api(SLUG,method='HEAD')
        self.assertEqual(st,200);self.assertEqual(d,b'')
    def test_08_post_disallowed(self):
        st,h,d=api(SLUG,method='POST',body=b'{}')
        self.assertEqual(st,405)
    def test_09_client_cannot_call_member_rpc_without_token(self):
        st,h,d=api('/rest/v1/rpc/ffh_r147_member_preflight',
            method='POST',body=b'{"p_source":"probe","p_target":"ja"}',
            headers={'apikey':KEY,'Content-Type':'application/json'})
        self.assertIn(st,(401,403))
    def test_10_bad_jwt_cannot_call_member_rpc(self):
        st,h,d=api('/rest/v1/rpc/ffh_r147_member_preflight',
            method='POST',body=b'{"p_source":"probe","p_target":"ja"}',
            headers={'apikey':KEY,'Authorization':'Bearer not-a-real-jwt','Content-Type':'application/json'})
        self.assertIn(st,(401,403))
    def test_11_private_tables_not_exposed(self):
        st,h,d=api('/rest/v1/member_profiles?select=user_id&limit=1',
            headers={'apikey':KEY,'Accept-Profile':'ffh_r146_sandbox'})
        self.assertEqual(st,406)
    def test_12_js_syntax(self):
        # Check that real hosted <script> contains parseable JavaScript.
        text=self.page.decode('utf-8')
        script=re.search(r'<script>(.*?)</script>',text,re.DOTALL)
        self.assertIsNotNone(script)
        with tempfile.TemporaryDirectory() as work:
            path=pathlib.Path(work,'main.js')
            path.write_text(script.group(1),encoding='utf-8')
            check=subprocess.run(['node','--check',str(path)],capture_output=True,timeout=10)
            self.assertEqual(check.returncode,0,check.stderr.decode()[:400])
if __name__=='__main__':unittest.main(verbosity=2)
