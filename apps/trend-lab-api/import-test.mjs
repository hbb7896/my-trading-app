import {test} from 'node:test';
import assert from 'node:assert/strict';
import {prepareImport,parseCsv} from './import.mjs';
import {createApp} from './server.mjs';
const csv='\uFEFFTrade_ID,Entry_Date,Exit_Date,Ticker,Buy_Amount,Sell_Amount,Memo,Mistake_Tags,Emotion,Discipline,Chart_Link\r\n"id-1","2026-09-01","2026-09-02","삼성SDI","100","110","메모, 줄바꿈\n둘째줄 ""따옴표""","조기청산 | 손절 지연","불안","계획","https://example.com/chart"\r\n"id-2","","2026-09-02","알수없는종목","100","90","","","","",""';
test('Trading Master CSV preserves notes, quotes, missing fields and stable identities',()=>{
 const rows=prepareImport(csv);assert.equal(rows.length,2);assert.equal(rows[0].trade.code,'006400');assert.equal(rows[0].trade.memo,'메모, 줄바꿈\n둘째줄 "따옴표"');assert.equal(rows[0].trade.tags.length,2);assert.equal(rows[1].trade.entry,'');assert.equal(rows[1].trade.code,'');assert.deepEqual(rows.map(r=>r.sourceId),prepareImport(csv).map(r=>r.sourceId));
 assert.throws(()=>parseCsv('a,"unclosed'));assert.throws(()=>prepareImport('wrong\nfile'));assert.equal(prepareImport(csv.replace('"100","110"','"0","110"'))[0].issues.length,1);
});
test('CSV preview is read-only; repeated import is idempotent and invalid batches are atomic',async()=>{
 const token='test-access-token-123456789';const server=createApp({token});await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
 const call=async(path,csvText)=>fetch(base+path,{method:csvText?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:csvText?JSON.stringify({csv:csvText}):undefined});
 try{
 const preview=await(await call('/api/import/preview',csv)).json();assert.equal(preview.valid,2);assert.deepEqual(await(await call('/api/trades')).json(),[]);
 assert.deepEqual(await(await call('/api/import/commit',csv)).json(),{inserted:2,skipped:0});assert.deepEqual(await(await call('/api/import/commit',csv)).json(),{inserted:0,skipped:2});
 const data=await(await call('/api/trades')).json();assert.equal(data.length,2);assert.equal(data.find(t=>t.ticker==='삼성SDI').emotion,'불안');
 assert.equal((await call('/api/import/commit',csv.replace('"100","110"','"0","110"'))).status,400);assert.equal((await(await call('/api/trades')).json()).length,2);
 }finally{await new Promise(r=>server.close(r));}
});
