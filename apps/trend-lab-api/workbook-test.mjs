import test from 'node:test';
import assert from 'node:assert/strict';
import XLSX from 'xlsx';
import {workbookPreview} from './workbook.mjs';
import {createApp} from './server.mjs';

function input(rows,bookType='xlsx'){const book=XLSX.utils.book_new();XLSX.utils.book_append_sheet(book,XLSX.utils.aoa_to_sheet(rows),'거래');return {name:'test.'+(bookType==='biff8'?'xls':bookType),data:XLSX.write(book,{bookType,type:'buffer'}).toString('base64')};}
test('Excel and legacy XLS share original summary conversion rules',()=>{
 for(const type of ['xlsx','biff8']){const result=workbookPreview(input([['종목명','매도일자','매수금액','실현손익'],['테스트','2026-01-05',10000,-500]],type));assert.equal(result.rows.length,1);assert.equal(result.rows[0].trade.sell,9500);assert.equal(result.rows[0].trade.entry,'');assert.equal(result.issues.length,0);}
});
test('execution lots preserve FIFO costs, partial sells and unmatched warnings',()=>{
 const result=workbookPreview(input([['종목명','거래일자','매매구분','체결수량','체결금액','수수료','세금'],['테스트','2026-01-01','매수',10,1000,10,0],['테스트','2026-01-02','매수',10,2000,0,0],['테스트','2026-01-03','매도',15,3000,10,20],['다른종목','2026-01-04','매도',1,100,0,0]]));
 assert.equal(result.mode,'executions');assert.equal(result.rows.length,1);assert.equal(result.rows[0].trade.buy,2010);assert.equal(result.rows[0].trade.sell,2970);assert.equal(result.openQty,5);assert.equal(result.issues.length,1);
});
test('exported journal identifiers and metadata survive Excel preview',()=>{
 const result=workbookPreview(input([['Trade_ID','Ticker','Entry_Date','Exit_Date','Buy_Amount','Sell_Amount','Memo','Mistake_Tags','Emotion'],['original-id','테스트','','2026-01-05',100,110,'복기\n두 줄','추격매수 | 기타','차분']]));
 assert.equal(result.rows[0].trade.memo,'복기\n두 줄');assert.deepEqual(result.rows[0].trade.tags,['추격매수','기타']);assert.equal(result.rows[0].trade.emotion,'차분');assert.equal(result.rows[0].sourceId,workbookPreview(input([['Trade_ID','Ticker','Exit_Date','Buy_Amount','Sell_Amount'],['original-id','테스트','2026-01-05',100,110]])).rows[0].sourceId);
});
test('workbook preview authenticates, never saves, and confirmed CSV commits atomically',async()=>{
 const token='workbook-test-token-123456789';const server=createApp({token});await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 try{const data=input([['종목명','매도일자','매수금액','매도금액'],['테스트','2026-01-05',100,120]]),headers={Authorization:'Bearer '+token,'Content-Type':'application/json'};
 assert.equal((await fetch(base+'/api/workbook/preview',{method:'POST',body:JSON.stringify(data)})).status,401);
 const response=await fetch(base+'/api/workbook/preview',{method:'POST',headers,body:JSON.stringify(data)});assert.equal(response.status,200);const result=await response.json();assert.equal((await (await fetch(base+'/api/trades',{headers})).json()).length,0);
 for(let i=0;i<2;i++){const value=await (await fetch(base+'/api/import/commit',{method:'POST',headers,body:JSON.stringify({csv:result.csv})})).json();assert.equal(value.inserted,i===0?1:0);}assert.equal((await (await fetch(base+'/api/trades',{headers})).json()).length,1);
 }finally{await new Promise(r=>server.close(r));}
});
test('journal-only saves preserve trade amounts and reject stale review drafts',async()=>{
 const token='journal-test-token-1234567890',server=createApp({token});await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port,headers={Authorization:'Bearer '+token,'Content-Type':'application/json'};
 try{const trade={ticker:'테스트',code:'',entry:'',exit:'2026-01-05',buy:100,sell:120,memo:'최초'};const value=await (await fetch(base+'/api/trades',{method:'POST',headers,body:JSON.stringify(trade)})).json();
 await fetch(base+'/api/trades/'+value.id,{method:'PUT',headers,body:JSON.stringify({...trade,buy:200,sell:250})});
 const original={memo:'최초',tags:[],emotion:'',discipline:'',chart_link:''},url=base+'/api/trades/'+value.id+'/journal',body=JSON.stringify({memo:'수정',tags:['기타'],original});
 const first=await fetch(url,{method:'PATCH',headers,body});assert.equal(first.status,200);const saved=await first.json();assert.equal(saved.buy,200);assert.equal(saved.sell,250);assert.equal(saved.memo,'수정');assert.deepEqual(saved.tags,['기타']);
 assert.equal((await fetch(url,{method:'PATCH',headers,body})).status,409);
 assert.equal((await fetch(url,{method:'PATCH',body})).status,401);
 }finally{await new Promise(r=>server.close(r));}
});
test('exporting existing native or imported trades and reimporting cannot duplicate records',async()=>{
 const token='roundtrip-test-token-1234567890',server=createApp({token});await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port,headers={Authorization:'Bearer '+token,'Content-Type':'application/json'};
 const request=async(path,data)=>{const r=await fetch(base+path,{method:data?'POST':'GET',headers,body:data?JSON.stringify(data):undefined});assert.equal(r.ok,true);return r.json();};
 try{await request('/api/trades',{ticker:'직접 기록',code:'',entry:'',exit:'2026-01-05',buy:100,sell:120,memo:'메모'});await request('/api/import/commit',{csv:'Trade_ID,Ticker,Exit_Date,Buy_Amount,Sell_Amount\noriginal-id,가져온 기록,2026-01-06,100,110'});
 const trades=await request('/api/trades'),csv=['Trade_ID,Ticker,Exit_Date,Buy_Amount,Sell_Amount',...trades.map(t=>[t.id,t.ticker,t.exit,t.buy,t.sell].join(','))].join('\n');
 assert.equal((await request('/api/import/preview',{csv})).duplicates,2);assert.deepEqual(await request('/api/import/commit',{csv}),{inserted:0,skipped:2});assert.equal((await request('/api/trades')).length,2);
 }finally{await new Promise(r=>server.close(r));}
});
