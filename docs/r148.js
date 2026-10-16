'use strict';
// R148 held staging requests only. Does NOT call Render, translate, or publish.
(() => {
  const nonce='FFH_R148_'+Array.from(crypto.getRandomValues(new Uint8Array(16)),
    n=>n.toString(16).padStart(2,'0')).join('');
  let seen=false;
  const status=message=>{document.getElementById('stageStatus').textContent=message};
  const stage=document.getElementById('stage');
  const duplicate=document.getElementById('duplicate');
  async function probe(retry) {
    if (!token) {status('Please sign in again.');return}
    if (retry&&!seen) {status('Submit one held request first.');return}
    stage.disabled=true;duplicate.disabled=true;
    try {
      const check=await fetch(BASE+'/auth/v1/user',{
        headers:{apikey:PUB,Authorization:'Bearer '+token},cache:'no-store'});
      if(!check.ok)throw new Error('Session expired');
      const response=await fetch(BASE+'/rest/v1/rpc/ffh_r148_stage_admit',{
        method:'POST',
        headers:{apikey:PUB,Authorization:'Bearer '+token,
          'Content-Type':'application/json'},
        body:JSON.stringify({p_source:SOURCE,p_target:'ja',p_nonce:nonce}),
        cache:'no-store'
      });
      if(!response.ok)throw new Error('Admission rejected (HTTP '+response.status+').');
      const data=await response.json();
      if(data.model_connected!==false)
        throw new Error('Unexpected model status; stop.');
      if(data.status==='staging_held' &&
         data.no_replay===true && data.human_approved===false &&
         data.production_writes===0) {
        seen=true;
        status('PASS: one durable staging request recorded as HELD. Nothing translated or published. Now test duplicate protection.');
      } else if(data.status==='duplicate' && seen) {
        status('PASS: replay of the same request rejected as a duplicate. No translation ran.');
      } else if(data.status==='quota_exceeded'){
        status('Staging quota enforced. Please wait; nothing translated.');
      } else {
        status('Request not admitted: '+String(data.status||'unknown'));
      }
    }catch(error){
      status('Request check unavailable: '+String(error?.message||'network error'));
    }finally{
      stage.disabled=!token||seen;
      duplicate.disabled=!token||!seen;
    }
  }
  stage.addEventListener('click',()=>probe(false));
  duplicate.addEventListener('click',()=>probe(true));
})();
