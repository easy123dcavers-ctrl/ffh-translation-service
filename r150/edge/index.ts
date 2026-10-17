/**
 * R150 read-only/staging authentication broker, with model dispatch hard OFF.
 * JSON Edge Function, NOT a hosted HTML login page.
 * STAGING PROJECT ONLY. Do not deploy to FFH production Supabase.
 */
import {createR150Handler} from './core.mjs';

// Publishable keys are public by design, never service-role or secret keys.
const keys=JSON.parse(Deno.env.get('SUPABASE_PUBLISHABLE_KEYS') ?? '{}');
const variable=keys.default;
const publicKey=typeof variable==='string' ? Deno.env.get(variable) : undefined;
if(typeof publicKey!=='string') throw new Error('Staging public publishable key unavailable');
Deno.serve(createR150Handler({publishableKey:publicKey}));
