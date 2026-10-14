import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {validDate} from './analysis.js';
const codes=JSON.parse(readFileSync(new URL('./stock-codes.json',import.meta.url),'utf8'));
export function parseCsv(text){
 if(typeof text!=='string'||Buffer.byteLength(text)>2_000_000)throw Error('CSV는 2MB 이하만 가져올 수 있습니다.');
 const rows=[];let row=[],cell='',quoted=false,closed=false;
 text=text.replace(/^\uFEFF/,'');
 for(let i=0;i<text.length;i++){const ch=text[i];
 if(quoted){if(ch==='"'){if(text[i+1]==='"'){cell+='"';i++;}else{quoted=false;closed=true;}}else cell+=ch;continue;}
 if(ch==='"'){if(cell.length||closed)throw Error('CSV 따옴표 형식을 확인하세요.');quoted=true;}
 else if(ch===','||ch==='\n'||ch==='\r'){row.push(cell);cell='';closed=false;if(ch!==','){if(ch==='\r'&&text[i+1]==='\n')i++;if(row.some(v=>v.trim()))rows.push(row);row=[];}}
 else{if(closed&&!/\s/.test(ch))throw Error('CSV 따옴표 형식을 확인하세요.');if(!closed)cell+=ch;}
 }
 if(quoted)throw Error('CSV 따옴표가 닫히지 않았습니다.');
 row.push(cell);if(row.some(v=>v.trim()))rows.push(row);
 if(rows.length>5001)throw Error('한 번에 최대 5,000건만 가져올 수 있습니다.');return rows;
}
export function prepareImport(text){
 const rows=parseCsv(text);if(rows.length<2)throw Error('CSV에 거래기록이 없습니다.');
 const headers=rows[0],get=(r,k)=>r[headers.indexOf(k)]??'';
 for(const h of ['Ticker','Exit_Date','Buy_Amount','Sell_Amount'])if(!headers.includes(h))throw Error('Trading Master 내보내기 CSV를 선택하세요.');
 const occurrences=new Map();return rows.slice(1).map((r,index)=>{
 const ticker=get(r,'Ticker').trim(),entry=get(r,'Entry_Date').trim(),exit=get(r,'Exit_Date').trim(),buy=Number(get(r,'Buy_Amount').replaceAll(',','')),sell=Number(get(r,'Sell_Amount').replaceAll(',',''));
 const issues=[];if(!ticker||ticker.length>100)issues.push('종목명');if(!validDate(exit)||(entry&&(!validDate(entry)||entry>exit)))issues.push('날짜');if(!get(r,'Buy_Amount').trim()||!get(r,'Sell_Amount').trim()||!Number.isFinite(buy)||buy<=0||buy>1e15||!Number.isFinite(sell)||sell<0||sell>1e15)issues.push('금액');
 const code=get(r,'Stock_Code').trim()||get(r,'Code').trim()||codes[ticker.replace(/\s+/g,'').toLowerCase()]||(/^\d{6}$/.test(ticker)?ticker:'');if(code&&!/^\d{6}$/.test(code))issues.push('종목코드');
 const identity=get(r,'Trade_ID').trim();const fingerprint=JSON.stringify([ticker,entry,exit,buy,sell]);const ordinal=(occurrences.get(fingerprint)||0)+1;occurrences.set(fingerprint,ordinal);
 const sourceId=/^IMPORT_[a-f0-9]{64}$/.test(identity)?identity:'IMPORT_'+createHash('sha256').update(identity?'master:'+identity:'trade:'+fingerprint+':'+ordinal).digest('hex');
 return {row:index+2,sourceId,sourceIdentity:identity,issues,trade:{ticker,code,entry,exit,buy,sell,memo:get(r,'Memo'),tags:get(r,'Mistake_Tags').split('|').map(v=>v.trim()).filter(Boolean),emotion:get(r,'Emotion'),discipline:get(r,'Discipline'),chart_link:get(r,'Chart_Link')}};
 });
}
