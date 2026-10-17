import test from 'node:test';
import assert from 'node:assert/strict';
import {createR150Handler,STAGING,PAGES} from './edge/core.mjs';
const KEY='sb_publishable_FFH_R150_Synthetic_only_1234567890';
const TOKEN='AAA'.repeat(40);
const PHRASE='FFH R146 interface label for staging verification.';
const GOOD={action:'preflight',source:PHRASE,target:'ja'};
const USER={id:'c9206fdd-55cd-4377-ab9c-e20a135a47b5',is_anonymous:false};
const VERDICT={status:'authorized_preflight_only',source_eligible:true,target_supported:true,model_connected:false};
function req(p=GOOD,headers={},method='POST'){
 return new Request('https://staging-test.invalid/r150',{
   method,headers:{Origin:PAGES,Authorization:'Bearer '+TOKEN,'Content-Type':'application/json',...headers},
   body:method==='POST'?JSON.stringify(p):undefined});
}
function mock({user=USER,verdict=VERDICT,fail=false}={}){
 const urls=[],heads=[];
 const handler=createR150Handler({publishableKey:KEY,fetchImpl:async (url,opts)=>{
  urls.push(url);heads.push(opts);
  if(fail)throw Error('offline');
  if(url===STAGING+'/auth/v1/user') return Response.json(user);
  if(url===STAGING+'/rest/v1/rpc/ffh_r147_member_preflight')return Response.json(verdict);
  throw Error('Network egress must be pinned');
 }});
 return {handler,urls,heads};
}
async function outcome(f,p=GOOD,headers={}){
 const r=await f.handler(req(p,headers));
 return {code:r.status,data:await r.json(),headers:r.headers};
}
test('01 real staged auth+source verdict permits read-only check; model stays OFF',async()=>{
 const f=mock(),r=await outcome(f);
 assert.equal(r.code,200);
 assert.deepEqual(r.data,{status:'r150_authenticated_stage_ready_model_off',
  model_connected:false,production_writes:0,human_approved:false});
 assert.deepEqual(f.urls,[STAGING+'/auth/v1/user',STAGING+'/rest/v1/rpc/ffh_r147_member_preflight']);
 assert.ok(f.heads.every(x=>x.headers.Authorization==='Bearer '+TOKEN&&x.headers.apikey===KEY&&x.redirect==='error'));
});
test('02 CORS exact Pages origin only',async()=>{
 const f=mock(),r=await outcome(f,GOOD,{Origin:'https://evil.invalid'});
 assert.equal(r.code,403);assert.equal(r.headers.get('access-control-allow-origin'),null);assert.equal(f.urls.length,0);
});
test('03 missing bearer cannot call auth',async()=>{const f=mock();assert.equal((await outcome(f,GOOD,{Authorization:''})).code,401);assert.equal(f.urls.length,0)});
test('04 client-supplied owner role rejected',async()=>{const f=mock();assert.equal((await outcome(f,{...GOOD,role:'Owner'})).code,400);assert.equal(f.urls.length,0)});
test('05 unregistered source held by live backend',async()=>{const f=mock({verdict:{...VERDICT,source_eligible:false}});assert.equal((await outcome(f)).code,403);assert.equal(f.urls.length,2)});
test('06 session / terms deny',async()=>{const f=mock({verdict:{status:'denied'}});assert.equal((await outcome(f)).code,403);assert.equal(f.urls.length,2)});
test('07 Auth anonymous refused',async()=>{const f=mock({user:{...USER,is_anonymous:true}});assert.equal((await outcome(f)).code,401);assert.equal(f.urls.length,1)});
test('08 network outage fail closed with no token leak',async()=>{const f=mock({fail:true}),r=await outcome(f);assert.equal(r.code,503);assert.ok(!JSON.stringify(r.data).includes(TOKEN))});
test('09 unsupported target refused before remote Auth',async()=>{const f=mock(),r=await outcome(f,{...GOOD,target:'zz'});assert.equal(r.code,400);assert.equal(f.urls.length,0)});
test('10 forbidden translate action refused',async()=>{const f=mock(),r=await outcome(f,{...GOOD,action:'translate'});assert.equal(r.code,400);assert.equal(f.urls.length,0)});
test('11 encrypted public stage key required and wrong config refused',()=>{
 assert.throws(()=>createR150Handler({publishableKey:'sb_secret_bad'}));
 assert.throws(()=>createR150Handler({publishableKey:KEY,timeoutMs:9000}));
});
test('12 OPTIONS preflight no data access',async()=>{
 const f=mock();const r=await f.handler(new Request('https://staging-test.invalid/r150',{method:'OPTIONS',headers:{Origin:PAGES}}));
 assert.equal(r.status,204);assert.equal(f.urls.length,0);
});
test('13 GET not exposed and no data access',async()=>{
 const f=mock();const r=await f.handler(req(GOOD,{},'GET'));assert.equal(r.status,405);assert.equal(f.urls.length,0);
});
test('14 invalid source controls refused',async()=>{
 const f=mock();assert.equal((await outcome(f,{...GOOD,source:'hello\nworld'})).code,400);assert.equal(f.urls.length,0);
});
test('15 backend claim of connected model is refused',async()=>{
 const f=mock({verdict:{...VERDICT,model_connected:true}});assert.equal((await outcome(f)).code,403);
});
