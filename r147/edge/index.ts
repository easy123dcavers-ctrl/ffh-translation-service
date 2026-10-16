// R147 private FFH stage: public static login landing only. No model access.
const origin = 'https://hlsjzjnondimwhqbgjqm.supabase.co';
const markup = String.raw`<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FFH staging Member check</title><style>
:root{color-scheme:light dark;font-family:system-ui,sans-serif}
body{max-width:620px;margin:1.5rem auto;padding:0 1rem;line-height:1.5}
label,button{display:block;margin-top:.9rem}input{box-sizing:border-box;padding:.8rem;width:100%;font-size:1rem}
button{padding:.8rem;min-height:44px}#status{white-space:pre-wrap}
</style></head><body>
<h1>FFH staging account test</h1>
<p>This page tests your existing FFH staging Member account. Nothing is translated or published.</p>
<p id="status" role="status" aria-live="polite">Checking session…</p>
<form id="form" hidden><label for="email">Your staging account email</label>
<input id="email" type="email" autocomplete="email" required>
<button id="send" type="submit">Send secure sign-in email</button></form>
<section id="results" hidden><h2>Member status</h2><p id="summary"></p>
<button type="button" id="check">Verify authorization</button></section>
<p>Do not share your sign-in link, password, verification code, or token.</p>
<script>
'use strict';
const BASE='https://hlsjzjnondimwhqbgjqm.supabase.co';
const REDIRECT=BASE+'/functions/v1/ffh-r147-member-test';
const PUB=__PUBLIC_API_KEY__;
const SOURCE='FFH R146 interface label for staging verification.';
const el=id=>document.getElementById(id);
let token=null;
const report=s=>el('status').textContent=s;
function showLogin(message){report(message);el('form').hidden=false;el('results').hidden=true}
async function check(){
 if(!token){showLogin('Please sign in first.');return}
 el('check').disabled=true;
 try{
  const u=await fetch(BASE+'/auth/v1/user',{headers:{apikey:PUB,Authorization:'Bearer '+token},cache:'no-store'});
  if(!u.ok)throw new Error('Session expired or rejected.');
  const member=await u.json();if(!member||!member.id)throw new Error('User verification failed.');
  const response=await fetch(BASE+'/rest/v1/rpc/ffh_r147_member_preflight',{
   method:'POST',
   headers:{apikey:PUB,Authorization:'Bearer '+token,'Content-Type':'application/json'},
   body:JSON.stringify({p_source:SOURCE,p_target:'ja'}),cache:'no-store'
  });
  if(!response.ok)throw new Error('Member check refused (HTTP '+response.status+').');
  const v=await response.json();
  if(v.status!=='authorized_preflight_only'||v.source_eligible!==true||v.target_supported!==true||v.model_connected!==false)
   throw new Error('Member or source authorization is not ready.');
  el('summary').textContent='PASS: verified Member, current terms, registered English source and Japanese target. Model dispatch remains OFF.';
  report('Your staging Member check PASSED. No translation or publication occurred.');
 }catch(e){report('Not ready: '+(e?.message||'Please sign in again.'))}
 finally{el('check').disabled=false}
}
const h=new URLSearchParams(location.hash.slice(1));
const t=h.get('access_token');
if(location.hash)history.replaceState(null,'',location.pathname);
if(t && t.length<8192 && /^[A-Za-z0-9_.-]+$/.test(t)){
 token=t;el('results').hidden=false;check();
}else showLogin('Enter the email you used for your FFH staging test account.');
el('form').addEventListener('submit',async event=>{
 event.preventDefault();el('send').disabled=true;
 try{
  const email=el('email').value.trim();
  if(!email||email.length>254)throw new Error('Enter your existing staging account email.');
  const response=await fetch(BASE+'/auth/v1/otp?redirect_to='+encodeURIComponent(REDIRECT),{
   method:'POST',headers:{apikey:PUB,'Content-Type':'application/json'},
   body:JSON.stringify({email,create_user:false}),cache:'no-store'
  });
  if(!response.ok)throw new Error('Could not request login email (HTTP '+response.status+').');
  report('Check your email. Open the NEW sign-in link on this phone. Do not share it.');
 }catch(e){report(e?.message||'Login email request failed.')}
 finally{el('send').disabled=false}
});
el('check').addEventListener('click',check);
</script></body></html>`;
Deno.serve((req: Request) => {
 if(req.method!=='GET'&&req.method!=='HEAD')return new Response(null,{status:405,headers:{Allow:'GET, HEAD'}});
 const key="sb_publishable_ZoYvYGbu9rJlPhHjM-3t3g_MqFWGkL2"; // staging publishable API key, public by design; NEVER service-role
 if(!key||key.split('.').length!==3)return new Response('Staging key unavailable',{status:503});
 const body=markup.replace('__PUBLIC_API_KEY__',JSON.stringify(key));
 return new Response(req.method==='HEAD'?null:body,{
  headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store',
   'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer',
   'Content-Security-Policy':"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src https://hlsjzjnondimwhqbgjqm.supabase.co; form-action 'none'; base-uri 'none'; frame-ancestors 'none'"
  }
 });
});