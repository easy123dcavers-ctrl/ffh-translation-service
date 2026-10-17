import test from 'node:test';
import assert from 'node:assert/strict';
import {createR151Handler,STAGING,RENDER,PAGES,TEXT,TARGET} from './edge/core.mjs';
const uuid='12345678-1234-4234-8234-123456789abc';
const jwt=['eyJhbGciOiJIUzI1NiJ9',
 Buffer.from(JSON.stringify({session_id:uuid})).toString('base64url'),'syntheticsignature'].join('.');
const key='sb_publishable_'+('teststage'.repeat(7));
const secret='R151-TEST-SERVICE-ROLE-NOT-A-REAL-SECRET-1234567890';
const rid='r151_simulated_nonce_abcdef123456';
const ok=(x,status=200)=>new Response(JSON.stringify(x),{
  status,headers:{'Content-Type':'application/json'}});
function testHarness(overrides={}){
  const calls=[];
  const fake=async(url,opts={})=>{
    calls.push({url,opts});
    if(url===STAGING+'/auth/v1/user')return ok({id:uuid,is_anonymous:false});
    if(url===STAGING+'/functions/v1/ffh-r150-auth-broker-stage')
      return ok({status:overrides.broker||'r150_authenticated_stage_ready_model_off',
        model_connected:false,human_approved:false,production_writes:0});
    if(url===STAGING+'/rest/v1/rpc/ffh_r151_admit')
      return ok({status:overrides.admit||'admitted'});
    if(url===STAGING+'/rest/v1/rpc/ffh_r151_finish')
      return ok({status:overrides.finish||'done',human_approved:false,production_writes:0});
    if(url===RENDER)return ok({translatedText:overrides.translate??'Etiqueta de interfaz FFH para verificación.'});
    throw new Error('Unexpected hostname or route');
  };
  const h=createR151Handler({publishableKey:key,serviceRoleKey:secret,
    fetchImpl:overrides.fetchImpl||fake,modelTimeoutMs:3000});
  return {h,calls};
}
const req=(token=jwt,origin=PAGES,id=rid,method='POST')=>new Request(
  'https://hlsjzjnondimwhqbgjqm.supabase.co/functions/v1/ffh-r151-synthetic-model-bridge',{
    method,headers:{Origin:origin,Authorization:token?'Bearer '+token:'',
      'Content-Type':'application/json'},
    ...(method==='POST'?{body:JSON.stringify({request_id:id})}:{})
  });
test('01 rejects no auth before any upstream',async()=>{
  const {h,calls}=testHarness();assert.equal((await h(req(''))).status,401);
  assert.equal(calls.length,0);
});
test('02 blocks untrusted browser origins',async()=>{
  const {h,calls}=testHarness();assert.equal((await h(req(jwt,'https://evil.example'))).status,403);
  assert.equal(calls.length,0);
});
test('03 refuses malformed request ID',async()=>{
  const {h,calls}=testHarness();assert.equal((await h(req(jwt,PAGES,'x'))).status,400);
  assert.equal(calls.length,0);
});
test('04 rejects a session-free JWT',async()=>{
  const {h,calls}=testHarness();
  assert.equal((await h(req('abc.abc.abc'))).status,401);assert.equal(calls.length,0);
});
test('05 no server-only secret means fully held',async()=>{
  const h=createR151Handler({publishableKey:key,serviceRoleKey:'',fetchImpl:()=>{throw Error('must not run')}});
  assert.equal((await h(req())).status,503);
});
test('06 prior R150 broker denial never reaches model',async()=>{
  const {h,calls}=testHarness({broker:'member_or_source_denied'});
  assert.equal((await h(req())).status,403);assert.equal(calls.some(c=>c.url===RENDER),false);
});
test('07 duplicate denied before model',async()=>{
  const {h,calls}=testHarness({admit:'duplicate'});
  assert.equal((await h(req())).status,409);assert.equal(calls.some(c=>c.url===RENDER),false);
});
test('08 quota full denied before model',async()=>{
  const {h,calls}=testHarness({admit:'quota_exceeded'});
  assert.equal((await h(req())).status,429);assert.equal(calls.some(c=>c.url===RENDER),false);
});
test('09 model same as input is held',async()=>{
  const {h,calls}=testHarness({translate:TEXT});
  assert.equal((await h(req())).status,423);
  assert.equal(calls.filter(c=>c.url.endsWith('ffh_r151_finish')).length,1);
  const params=JSON.parse(calls.find(c=>c.url.endsWith('ffh_r151_finish')).opts.body);
  assert.equal(params.p_model_ok,false);
});
test('10 final revoked session fails closed',async()=>{
  const {h,calls}=testHarness({finish:'held'});
  assert.equal((await h(req())).status,423);
  assert.equal(calls.filter(c=>c.url===RENDER).length,1);
});
test('11 fixed synthetic real model only, never private JWT',async()=>{
  const {h,calls}=testHarness();
  const r=await h(req());assert.equal(r.status,200);
  const body=await r.json();
  assert.equal(body.status,'provisional_candidate');
  assert.equal(body.human_approved,false);assert.equal(body.production_writes,0);
  assert.equal(body.model_connected,true);assert.equal(body.target,TARGET);
  const c=calls.find(c=>c.url===RENDER);
  assert.ok(c);assert.deepEqual(JSON.parse(c.opts.body),{q:TEXT,source:'en',target:'es'});
  assert.equal(c.opts.headers.Authorization,undefined);
  assert.equal(c.opts.headers.apikey,undefined);
  assert.equal(calls.filter(c=>c.url.includes('ffh-r150-auth-broker-stage')).length,2);
  assert.equal(calls.filter(c=>c.url.endsWith('ffh_r151_finish')).length,1);
});
test('12 upstream network failure leaves output closed',async()=>{
  const {h,calls}=testHarness({fetchImpl:async()=>{throw Error('unavailable')}});
  assert.equal((await h(req())).status,503);
});
test('13 no model call while request held by backend gate',async()=>{
  const {h,calls}=testHarness({admit:'source_held'});
  assert.equal((await h(req())).status,422);assert.ok(!calls.some(c=>c.url===RENDER));
});
test('14 preflight respects allowlisted page origin',async()=>{
  const {h,calls}=testHarness();
  const r=await h(new Request('https://staging.example/',{method:'OPTIONS',
    headers:{Origin:PAGES}}));
  assert.equal(r.status,204);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'),PAGES);
  assert.equal(calls.length,0);
});
test('15 refuses user-supplied source and target (fixed only)',async()=>{
  const {h,calls}=testHarness();
  const r=await h(new Request('https://staging.example/',{method:'POST',headers:{
    Origin:PAGES,Authorization:'Bearer '+jwt,'Content-Type':'application/json'},
    body:JSON.stringify({request_id:rid,text:'recipe',target:'ja'})}));
  assert.equal(r.status,400);assert.equal(calls.length,0);
});
test('16 no token or ID in output and no cookies',async()=>{
  const {h}=testHarness();const r=await h(req());
  const text=await r.text();assert.ok(!text.includes(jwt));assert.ok(!text.includes(rid));
  assert.ok(!r.headers.get('Set-Cookie'));
});
