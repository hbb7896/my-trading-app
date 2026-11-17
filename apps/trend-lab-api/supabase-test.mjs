import {test} from 'node:test';import assert from 'node:assert/strict';
import {SupabaseStore} from './supabase-store.mjs';import {createApp} from './server.mjs';
const id='11111111-1111-4111-8111-111111111111';
test('cloud authenticates actual user and forwards session instead of admin keys',async()=>{
 const calls=[];const store=new SupabaseStore({url:'https://example.supabase.co',key:'sb_publishable_test',fetchImpl:async(url,options)=>{calls.push({url,options});return Response.json(url.endsWith('/auth/v1/user')?{id}:true);}});
 const context=await store.authenticate('Bearer owner-session');assert.equal(context.userId,id);assert.equal(calls[0].options.headers.Authorization,'Bearer owner-session');assert.equal(calls[0].options.headers.apikey,'sb_publishable_test');
 await assert.rejects(()=>store.authenticate(''),e=>e.status===401);
 assert.throws(()=>new SupabaseStore({url:'https://example.supabase.co',key:'sb_secret_test'}));
});
test('reject expired sessions and unapproved accounts',async()=>{
 for(const response of [Response.json({error:'expired'},{status:401}),Response.json(false)]){
 const store=new SupabaseStore({url:'https://example.supabase.co',key:'sb_publishable_test',fetchImpl:async(url)=>url.endsWith('/auth/v1/user')&&response.status===200?Response.json({id}):response});await assert.rejects(()=>store.authenticate('Bearer test'),e=>[401,403].includes(e.status));
 }
});
test('cloud route never falls back to local shared token',async()=>{
 const server=createApp({supabase:{url:'https://example.supabase.co',key:'sb_publishable_test',fetchImpl:async()=>Response.json({error:'invalid'},{status:401})}});await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
 try{assert.equal((await fetch(base+'/api/trades',{headers:{Authorization:'Bearer local-preview-only-token-123456789'}})).status,401);const config=await(await fetch(base+'/api/config')).json();assert.equal(config.mode,'supabase');assert(!JSON.stringify(config).includes('APP_TOKEN'));}finally{await new Promise(r=>server.close(r));}
});
