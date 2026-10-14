import {createServer} from 'node:http';
import {DatabaseSync} from 'node:sqlite';
import {randomUUID,timingSafeEqual} from 'node:crypto';
import {mkdirSync,existsSync,readFileSync} from 'node:fs';
import {resolve,extname,join,sep} from 'node:path';
import {pathToFileURL} from 'node:url';
import {analyze,validate,validDate} from './analysis.js';
import {prepareImport} from './import.mjs';
import {SupabaseStore} from './supabase-store.mjs';
import {workbookPreview} from './workbook.mjs';

export function cleanTrade(t){
 if(!t||typeof t.ticker!=='string'||!t.ticker.trim()||t.ticker.length>100)throw Error('종목명을 입력하세요.');
 if(typeof t.code!=='string'||(t.code&&!/^\d{6}$/.test(t.code)))throw Error('종목코드를 확인하세요.');
 if(typeof t.entry!=='string'||!validDate(t.exit)||(t.entry&&(!validDate(t.entry)||t.entry>t.exit)))throw Error('거래 날짜를 확인하세요.');
 for(const k of ['buy','sell'])if(typeof t[k]!=='number'||!Number.isFinite(t[k])||t[k]<0||t[k]>1e15)throw Error('금액을 확인하세요.');
 if(t.buy<=0)throw Error('매수금액은 0보다 커야 합니다.');
 if(typeof t.memo!=='string'||t.memo.length>10000)throw Error('메모는 10,000자까지 입력할 수 있습니다.');
 const extra={};for(const k of ['emotion','discipline','chart_link']){if(t[k]!=null&&(typeof t[k]!=='string'||t[k].length>2048))throw Error('복기 정보를 확인하세요.');extra[k]=t[k]||'';}if(t.tags!=null&&(!Array.isArray(t.tags)||t.tags.length>30||t.tags.some(v=>typeof v!=='string'||v.length>100)))throw Error('태그를 확인하세요.');
 return {...extra,tags:t.tags||[],ticker:t.ticker.trim(),code:t.code,entry:t.entry,exit:t.exit,buy:t.buy,sell:t.sell,memo:t.memo,pnl:t.sell-t.buy,roi:(t.sell/t.buy-1)*100};
}
export function createApp({dbPath=':memory:',token,webDir,origins=[],supabase}={}){
 if(!supabase&&(!token||token.length<24))throw Error('APP_TOKEN을 24자 이상으로 설정하세요.');
 const cloud=supabase?new SupabaseStore(supabase):null;
 const db=cloud?null:new DatabaseSync(dbPath);if(db)db.exec('PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS trades(id TEXT PRIMARY KEY, payload TEXT NOT NULL)');
 const list=()=>db.prepare('SELECT id,payload FROM trades').all().map(r=>({id:r.id,...JSON.parse(r.payload)})).sort((a,b)=>b.exit.localeCompare(a.exit)||a.id.localeCompare(b.id));
 const server=createServer(async(req,res)=>{
 const url=new URL(req.url,'http://localhost');const origin=req.headers.origin;
 if(origin&&origins.includes(origin)){res.setHeader('Access-Control-Allow-Origin',origin);res.setHeader('Vary','Origin');}
 const send=(data,status=200)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(data));};
 if(url.pathname==='/health')return send({ok:true});
 if(url.pathname==='/api/config'&&req.method==='GET')return send(cloud?{mode:'supabase',url:cloud.url,publishableKey:cloud.key}:{mode:'local'});
 if(!url.pathname.startsWith('/api/')){
 if(webDir&&['GET','HEAD'].includes(req.method)){const base=resolve(webDir);let file;try{file=resolve(base,'.'+decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname));}catch{return send({error:'잘못된 경로입니다.'},400);}if((file===base||file.startsWith(base+sep))&&existsSync(file)){try{res.writeHead(200,{'Content-Type':({'.html':'text/html; charset=utf-8','.js':'application/javascript','.json':'application/json','.wasm':'application/wasm','.css':'text/css','.png':'image/png','.svg':'image/svg+xml','.ttf':'font/ttf'})[extname(file)]||'application/octet-stream'});return res.end(req.method==='HEAD'?undefined:readFileSync(file));}catch{}}}
 return send({error:'경로를 찾을 수 없습니다.'},404);
 }
 if(origin&&!origins.includes(origin)&&origin!==`http://${req.headers.host}`&&origin!==`https://${req.headers.host}`)return send({error:'허용되지 않은 출처입니다.'},403);
 if(req.method==='OPTIONS'){res.writeHead(204,{'Access-Control-Allow-Methods':'GET,POST,PUT,PATCH,DELETE,OPTIONS','Access-Control-Allow-Headers':'Authorization,Content-Type','Access-Control-Max-Age':'600'});return res.end();}
 let identity;
 try{
 if(cloud)identity=await cloud.authenticate(req.headers.authorization);
 else{const provided=Buffer.from(req.headers.authorization||''),expected=Buffer.from('Bearer '+token);if(provided.length!==expected.length||!timingSafeEqual(provided,expected))return send({error:'연결 키를 확인하세요.'},401);}
 const get=async id=>cloud?cloud.get(identity,id):(()=>{const row=db.prepare('SELECT id,payload FROM trades WHERE id=?').get(id);return row?{id:row.id,...JSON.parse(row.payload)}:null;})();
 const body=async(limit=65536)=>{const chunks=[];let size=0;for await(const part of req){size+=part.length;if(size>limit)throw Error('요청이 너무 큽니다.');chunks.push(part);}return JSON.parse(Buffer.concat(chunks).toString('utf8'));};
 if(url.pathname==='/api/workbook/preview'&&req.method==='POST'){
 const preview=workbookPreview(await body(8_000_000));const known=new Set((cloud?await cloud.list(identity):list()).map(t=>t.id));for(const row of preview.rows){if(!row.issues.length){try{row.trade=cleanTrade(row.trade);}catch(e){row.issues.push(e.message);}}row.duplicate=known.has(row.sourceId);}return send(preview);
 }
 if(url.pathname==='/api/import/preview'&&req.method==='POST'){
 const {csv}=await body(3_000_000);const rows=prepareImport(csv);const knownIds=new Set((cloud?await cloud.list(identity):list()).map(t=>t.id));for(const row of rows){if(!row.issues.length){try{row.trade=cleanTrade(row.trade);}catch(e){row.issues.push(e.message);}}row.duplicate=knownIds.has(row.sourceId);}
 return send({rows,total:rows.length,valid:rows.filter(r=>!r.issues.length&&!r.duplicate).length,duplicates:rows.filter(r=>r.duplicate).length});
 }
 if(url.pathname==='/api/import/commit'&&req.method==='POST'){
 const {csv}=await body(3_000_000);const rows=prepareImport(csv);if(rows.some(r=>r.issues.length))return send({error:'입력 오류를 수정한 뒤 가져오세요.'},400);
 const cleaned=rows.map(r=>({...r,trade:cleanTrade(r.trade)}));if(cloud)return send(await cloud.import(identity,cleaned));let inserted=0;db.exec('BEGIN IMMEDIATE');try{for(const row of cleaned){const r=db.prepare('INSERT OR IGNORE INTO trades VALUES (?,?)').run(row.sourceId,JSON.stringify(row.trade));inserted+=Number(r.changes);}db.exec('COMMIT');}catch(e){db.exec('ROLLBACK');throw e;}return send({inserted,skipped:rows.length-inserted});
 }
 if(url.pathname==='/api/trades'&&req.method==='GET')return send(cloud?await cloud.list(identity):list());
 if(url.pathname==='/api/trades'&&req.method==='POST'){const t=cleanTrade(await body()),id=randomUUID();if(cloud)await cloud.insert(identity,id,t);else db.prepare('INSERT INTO trades VALUES (?,?)').run(id,JSON.stringify(t));return send({id,...t},201);}
 const journalMatch=url.pathname.match(/^\/api\/trades\/([^/]+)\/journal$/);
 if(journalMatch&&req.method==='PATCH'){
 const input=await body(),id=decodeURIComponent(journalMatch[1]),current=await get(id);if(!current)return send({error:'거래가 없습니다.'},404);
 const fields=t=>({memo:t?.memo||'',tags:t?.tags||[],emotion:t?.emotion||'',discipline:t?.discipline||'',chart_link:t?.chart_link||''});
 if(!input.original||JSON.stringify(fields(input.original))!==JSON.stringify(fields(current)))return send({error:'다른 화면에서 매매일지가 변경됐습니다. 최신 기록을 다시 연 뒤 저장하세요.'},409);
 const next=cleanTrade({...current,...fields(input)}),{id:oldId,...payload}=current;
 const updated=cloud?await cloud.updateIfUnchanged(identity,id,next,current):Number(db.prepare('UPDATE trades SET payload=? WHERE id=? AND payload=?').run(JSON.stringify(next),id,JSON.stringify(payload)).changes)===1;
 if(!updated)return send({error:'다른 화면에서 거래가 변경됐습니다. 최신 기록을 다시 연 뒤 저장하세요.'},409);
 return send({id,...next});
 }
 const match=url.pathname.match(/^\/api\/trades\/([^/]+)$/);
 if(match&&['PUT','DELETE'].includes(req.method)){const id=decodeURIComponent(match[1]);if(!(await get(id)))return send({error:'거래가 없습니다.'},404);if(req.method==='DELETE'){if(cloud)await cloud.delete(identity,id);else db.prepare('DELETE FROM trades WHERE id=?').run(id);return send({ok:true});}const t=cleanTrade(await body());if(cloud)await cloud.update(identity,id,t);else db.prepare('UPDATE trades SET payload=? WHERE id=?').run(JSON.stringify(t),id);return send({id,...t});}
 if(url.pathname==='/api/review'&&req.method==='POST'){
 const t=await body();validate(t);
 const upstream=await fetch(`https://fchart.stock.naver.com/sise.nhn?symbol=${t.code}&timeframe=day&count=750&requestType=0`,{signal:AbortSignal.timeout(15000)});
 if(!upstream.ok)return send({error:'시세 연결에 실패했습니다.'},502);
 const xml=new TextDecoder('euc-kr').decode(await upstream.arrayBuffer());
 const kst=new Date(Date.now()+9*3600000),today=kst.toISOString().slice(0,10),completed=kst.getUTCHours()*60+kst.getUTCMinutes()>=940;
 const bars=[...xml.matchAll(/<item\s+data="([^"]+)"/g)].map(m=>{const[d,...v]=m[1].split('|'),[open,high,low,close,volume]=v.map(Number);return {date:d.slice(0,4)+'-'+d.slice(4,6)+'-'+d.slice(6),open,high,low,close,volume};}).filter(b=>(b.date<today||(b.date===today&&completed))&&b.close>0&&b.high>0&&b.low>0&&[b.open,b.high,b.low,b.close,b.volume].every(Number.isFinite));
 if(!bars.length)return send({error:'종목코드 또는 시세를 확인하세요.'},502);
 return send({...analyze(bars,t),name:xml.match(/<chartdata[^>]*name="([^"]+)"/)?.[1]||t.code,source:'NAVER 일별 시세'});
 }
 return send({error:'지원하지 않는 요청입니다.'},404);
 }catch(e){return send({error:e.name==='TimeoutError'?'시세 요청 시간이 초과됐습니다.':e.message},e.status||400);}
 });
 server.on('close',()=>db?.close());return server;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
 const cloudMode=process.env.DB_MODE==='supabase';if(!cloudMode&&process.env.ALLOW_LOCAL_DEV!=='true')throw Error('DB_MODE=supabase를 설정하세요. 로컬 시험은 ALLOW_LOCAL_DEV=true가 필요합니다.');
 const dataDir=resolve(process.env.DATA_DIR||'data');if(!cloudMode)mkdirSync(dataDir,{recursive:true});
 const server=createApp({supabase:cloudMode?{url:process.env.SUPABASE_URL,key:process.env.SUPABASE_PUBLISHABLE_KEY}:undefined,dbPath:join(dataDir,'trades.sqlite'),token:process.env.APP_TOKEN,webDir:process.env.WEB_DIR,origins:(process.env.ALLOWED_ORIGINS||'http://localhost:8080').split(',')});
 server.listen(Number(process.env.PORT||8787),process.env.HOST||'127.0.0.1',()=>console.log(`Trend Lab API: http://${process.env.HOST||'127.0.0.1'}:${process.env.PORT||8787}`));
}
