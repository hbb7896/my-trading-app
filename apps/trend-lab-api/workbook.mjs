import XLSX from 'xlsx';
import * as cptable from 'xlsx/dist/cpexcel.full.mjs';
import {detectHeader,detectColumns,convertRows,fields} from './kiwoom-engine.mjs';
import {prepareImport} from './import.mjs';
XLSX.set_cptable(cptable);

export function workbookPreview(input){
 const {name,data,sheet,header,map,mode,fees=true,reverseSameDay=false}=input||{};
 if(typeof name!=='string'||! /\.(xlsx|xls|csv)$/i.test(name)||typeof data!=='string'||data.length>7_000_000)throw Error('.xlsx, .xls, .csv 파일을 5MB 이하로 선택하세요.');
 const bytes=Buffer.from(data,'base64');if(!bytes.length||bytes.length>5*1024*1024)throw Error('파일은 5MB 이하로 나눠주세요.');
 let contents=bytes,type='buffer';if(/\.csv$/i.test(name)){try{contents=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{contents=new TextDecoder('euc-kr').decode(bytes);}type='string';}
 const book=XLSX.read(contents,{type,codepage:949,cellDates:false,sheetRows:10001});
 if(!book.SheetNames.length)throw Error('읽을 수 있는 시트가 없습니다.');
 const selected=book.SheetNames.includes(sheet)?sheet:book.SheetNames[0];
 const matrix=XLSX.utils.sheet_to_json(book.Sheets[selected],{header:1,defval:'',raw:true,blankrows:true});
 if(matrix.length>10000)throw Error('시트가 너무 큽니다. 거래 내역을 5,000행 이하로 나눠주세요.');
 const h=Number.isInteger(header)&&header>=0&&header<matrix.length?header:detectHeader(matrix),mapping=map&&Object.keys(map).length?map:detectColumns(matrix[h]||[]),conversionMode=['summary','executions'].includes(mode)?mode:mapping.side>=0&&mapping.qty>=0?'executions':'summary';
 const missing=(conversionMode==='summary'?['ticker','exit','buy']:['ticker','exit','side','qty']).filter(k=>!Number.isInteger(mapping[k])||mapping[k]<0||mapping[k]>=(matrix[h]||[]).length);
 if(conversionMode==='summary'&&!(mapping.sell>=0)&&!(mapping.pnl>=0))missing.push('sell');
 if(conversionMode==='executions'&&!(mapping.amount>=0)&&!(mapping.price>=0))missing.push('amount');
 const result=missing.length?null:convertRows(matrix,h,mapping,conversionMode,{fees,reverseSameDay});
 let csv;
 const headings=matrix[h]||[];
 if(['Ticker','Exit_Date','Buy_Amount','Sell_Amount'].every(k=>headings.includes(k))){csv=XLSX.utils.sheet_to_csv(XLSX.utils.aoa_to_sheet(matrix.slice(h)));}
 else if(result){const cell=v=>'"'+String(v??'').replaceAll('"','""')+'"';const columns=['Entry_Date','Exit_Date','Ticker','Buy_Amount','Sell_Amount','Memo','Mistake_Tags'];csv=[columns,...result.trades.map(t=>[t.entry||'',t.exit,t.ticker,t.buy,t.sell,t.memo,t.tags.join('|')])].map(row=>row.map(cell).join(',')).join('\n');}
 const rows=csv?prepareImport(csv):[];
 return {sheetNames:book.SheetNames,sheet:selected,header:h,mapping,mode:conversionMode,fields:fields.map(([key,label])=>({key,label})),matrix:matrix.slice(0,Math.min(matrix.length,h+21)),headers:headings,missing,issues:result?.issues||[],ignored:result?.ignored||[],openQty:result?.openQty||0,openSymbols:result?.openSymbols||0,rows,csv};
}
