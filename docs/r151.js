'use strict';
// R151 staging-only: the browser never contacts Render or receives server keys.
(() => {
 const button=document.getElementById('r151');
 const replay=document.getElementById('r151Replay');
 const output=document.getElementById('r151Status');
 if(!button||!replay||!output)return;
 const nonce='R151_'+Array.from(crypto.getRandomValues(new Uint8Array(20)),
   x=>x.toString(16).padStart(2,'0')).join('');
 let submitted=false;
 async function run(isReplay){
  if(!token){output.textContent='Please sign in with a fresh email link.';return}
  if(isReplay&&!submitted){output.textContent='Try the one-time staging translation first.';return}
  button.disabled=true;replay.disabled=true;
  output.textContent=isReplay?'Confirming duplicate protection…':
   'Requesting one safe synthetic Spanish draft. The free model may need time to wake up…';
  try{
   const response=await fetch(BASE+'/functions/v1/ffh-r151-synthetic-model-bridge',{
    method:'POST',redirect:'error',cache:'no-store',
    headers:{apikey:PUB,Authorization:'Bearer '+token,'Content-Type':'application/json'},
    body:JSON.stringify({request_id:nonce})
   });
   const result=await response.json();
   if(result.status==='provisional_candidate'&&response.ok&&
      result.human_approved===false&&result.production_writes===0&&
      result.model_connected===true&&result.target==='es'&&
      typeof result.draft==='string'&&result.draft.length<800){
    submitted=true;
    output.textContent='PASS: one real Spanish machine draft (UNREVIEWED):\n'+
       result.draft+'\nNothing was approved, saved to FFH content, or published. Now check duplicate refusal.';
   }else if(result.status==='duplicate'&&response.status===409){
    submitted=true;
    output.textContent='PASS: identical request rejected as a duplicate. No second translation performed.';
   }else if(result.status==='quota_exceeded'&&response.status===429){
    output.textContent='Quota limit protected the staging system; no translation ran. Try again later.';
   }else{
    // Model errors or final authorization holds must never reveal a draft.
    output.textContent='Staging translation held: '+String(result.status||response.status)+
      '. No publication. Do not retry this request ID.';
    submitted=true;
   }
  }catch(e){
   submitted=true;output.textContent='Network or staging model test unavailable. The request may have been admitted; do not retry it. '+String(e?.message||'');
  }finally{
   button.disabled=true;replay.disabled=!token||!submitted;
  }
 }
 button.addEventListener('click',()=>run(false));
 replay.addEventListener('click',()=>run(true));
})();
