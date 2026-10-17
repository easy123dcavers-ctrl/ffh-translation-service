/**
 * R150 read-only/staging authentication broker, with model dispatch hard OFF.
 * JSON Edge Function, NOT a hosted HTML login page.
 * STAGING PROJECT ONLY. Do not deploy to FFH production Supabase.
 */
import {createR150Handler} from './core.mjs';

// Publishable keys are public by design, never service-role or secret keys.
const publicKey="sb_publishable_ZoYvYGbu9rJlPhHjM-3t3g_MqFWGkL2"; // Staging PUBLIC API key. Never a secret.
Deno.serve(createR150Handler({publishableKey:publicKey}));
