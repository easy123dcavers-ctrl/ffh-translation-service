/** FFH R151 STAGING ONLY. Must not be installed in FFH production. */
import {createR151Handler} from './core.mjs';
const stagingPublishableKey="sb_publishable_ZoYvYGbu9rJlPhHjM-3t3g_MqFWGkL2";
const serverSecret=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')||'';
Deno.serve(createR151Handler({
  publishableKey:stagingPublishableKey,serviceRoleKey:serverSecret
}));
