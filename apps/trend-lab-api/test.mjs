import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createApp,cleanTrade} from './server.mjs';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {analyze} from './analysis.js';
test('two clients share durable trade CRUD; authentication and validation',async()=>{
 const token='test-access-token-123456789';const server=createApp({token});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const base=`http://127.0.0.1:${server.address().port}`;
 const call=async(path,method='GET',body)=>fetch(base+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 try{
 assert.equal((await fetch(base+'/api/trades')).status,401);
 assert.equal((await fetch(base+'/api/trades',{headers:{Origin:'https://untrusted.example',Authorization:'Bearer '+token}})).status,403);
 const t={ticker:'삼성전자',code:'005930',entry:'2026-09-01',exit:'2026-09-02',buy:100000,sell:110000,memo:'test'};
 const response=await call('/api/trades','POST',t);assert.equal(response.status,201);const saved=await response.json();
 assert.equal(saved.pnl,10000);assert(Math.abs(saved.roi-10)<1e-8);
 const clientTwo=await (await call('/api/trades')).json();assert.equal(clientTwo[0].id,saved.id);
 assert.equal((await call('/api/trades/'+saved.id,'PUT',{...t,sell:90000})).status,200);
 assert.equal((await (await call('/api/trades')).json())[0].pnl,-10000);
 assert.equal((await call('/api/trades','POST',{...t,buy:0})).status,400);
 assert.equal((await call('/api/trades','POST',{...t,exit:'2026-02-30'})).status,400);
 assert.equal((await call('/api/trades/'+saved.id,'DELETE')).status,200);
 assert.deepEqual(await (await call('/api/trades')).json(),[]);
 }finally{await new Promise(r=>server.close(r));}
});
test('reject invalid financial input',()=>{assert.throws(()=>cleanTrade({}));assert.throws(()=>createApp({token:'short'}));});
test('records survive a server restart',async()=>{
 const folder=mkdtempSync(join(tmpdir(),'trend-lab-test-')),token='test-access-token-123456789',dbPath=join(folder,'test.sqlite');
 let server=createApp({token,dbPath});
 const start=async()=>{await new Promise(r=>server.listen(0,'127.0.0.1',r));return `http://127.0.0.1:${server.address().port}/api/trades`;};
 try{let url=await start();await fetch(url,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({ticker:'test',code:'005930',entry:'2026-01-01',exit:'2026-01-02',buy:100,sell:110,memo:''})});await new Promise(r=>server.close(r));server=createApp({token,dbPath});url=await start();assert.equal((await(await fetch(url,{headers:{Authorization:'Bearer '+token}})).json()).length,1);}finally{await new Promise(r=>server.close(r));rmSync(folder,{recursive:true,force:true});}
});
test('chart averages avoid future prices and same-day range remains unknown',()=>{
 const bars=Array.from({length:300},(_,i)=>({date:new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10),open:100+i,high:105+i,low:95+i,close:100+i,volume:1000}));
 const t={code:'005930',entry:bars[252].date,exit:bars[260].date};const before=analyze(bars,t);
 const changed=bars.map((b,i)=>i>252?{...b,close:99999}:b);assert.deepEqual(analyze(changed,t).criteria,before.criteria);
 assert.equal(analyze(bars,{...t,exit:t.entry}).range,null);
 assert.throws(()=>analyze(bars,{...t,exit:'2099-01-01'}));
});
