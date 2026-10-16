"""R147 zero-credit GitHub Pages staged login: static and negative Auth regression."""
import pathlib,re,subprocess,tempfile,unittest,urllib.request,urllib.error,json
DOC=pathlib.Path("docs/index.html")
EXPECTED="https://easy123dcavers-ctrl.github.io/ffh-translation-service/"
STAGING="https://hlsjzjnondimwhqbgjqm.supabase.co"
class PageAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=DOC.read_text(encoding="utf-8")
        match=re.search(r'<script>(.*?)</script>',cls.text,re.DOTALL)
        if not match:raise AssertionError("Staging page script missing")
        cls.script=match.group(1)
        key=re.search(r'const PUB="(sb_publishable_[A-Za-z0-9_-]+)"',cls.script)
        if not key:raise AssertionError("Staging publishable key missing")
        cls.key=key.group(1)
    def test_01_correct_staging_api(self):
        self.assertIn("const BASE='"+STAGING+"'",self.script)
    def test_02_exact_public_pages_redirect(self):
        self.assertIn("const REDIRECT='"+EXPECTED+"'",self.script)
    def test_03_existing_users_only(self):
        self.assertIn("create_user:false",self.script)
    def test_04_purge_url_login_token(self):
        self.assertIn("history.replaceState",self.script)
    def test_05_no_browser_token_storage(self):
        for prohibited in ("localStorage","sessionStorage","document.cookie"):
            self.assertNotIn(prohibited,self.script)
    def test_06_no_secret_or_service_role(self):
        for word in ("service_role","sb_secret_","SUPABASE_SERVICE_ROLE_KEY"):
            self.assertNotIn(word,self.text)
    def test_07_no_password_form(self):
        self.assertNotIn('type="password"',self.text)
    def test_08_broker_writes_disabled(self):
        self.assertIn("v.model_connected!==false",self.script)
        self.assertIn("ffh_r147_member_preflight",self.script)
    def test_09_browser_javascript_syntax(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d,"page.js");p.write_text(self.script,encoding="utf8")
            v=subprocess.run(["node","--check",str(p)],capture_output=True,timeout=10)
            self.assertEqual(v.returncode,0,v.stderr.decode()[:500])
    def test_10_no_jwt_rpc_denied_live(self):
        req=urllib.request.Request(STAGING+"/rest/v1/rpc/ffh_r147_member_preflight",
            data=json.dumps({"p_source":"sample","p_target":"ja"}).encode(),
            headers={"apikey":self.key,"Content-Type":"application/json"},method="POST")
        try:
            with urllib.request.urlopen(req,timeout=10) as resp: code=resp.status
        except urllib.error.HTTPError as e:code=e.code
        self.assertIn(code,(401,403))
if __name__=="__main__":unittest.main(verbosity=2)
