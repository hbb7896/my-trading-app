export class AccessError extends Error { constructor(message,status=401){super(message);this.status=status;} }
export class SupabaseStore {
 constructor({url,key,fetchImpl=fetch}){const parsed=new URL(url);if(parsed.protocol!=='https:'||parsed.username||parsed.password||parsed.search||parsed.hash)throw Error('Supabase HTTPS 주소를 확인하세요.');let valid=typeof key==='string'&&key.startsWith('sb_publishable_');if(typeof key==='string'&&key.startsWith('ey')){try{valid=JSON.parse(Buffer.from(key.split('.')[1],'base64url').toString()).role==='anon';}catch{valid=false;}}if(!valid)throw Error('Supabase 공개용 키를 사용하세요.');this.url=parsed.origin;this.key=key;this.fetch=fetchImpl;}
 async request(path,token,{method='GET',body,prefer}={}){
  const headers={apikey:this.key,Authorization:'Bearer '+token};if(body!==undefined)headers['Content-Type']='application/json';if(prefer)headers.Prefer=prefer;
  const response=await this.fetch(this.url+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),redirect:'error',signal:AbortSignal.timeout(20000)});
  if(!response.ok){if([401,403].includes(response.status))throw new AccessError('로그인 또는 계정 접근 권한을 확인하세요.',response.status);throw new AccessError('온라인 저장소 요청에 실패했습니다.',502);}
  if(response.status===204)return null;const text=await response.text();return text?JSON.parse(text):null;
 }
 async authenticate(header){
  const token=header?.match(/^Bearer (\S+)$/)?.[1];if(!token)throw new AccessError('본인 계정으로 로그인하세요.');
  const user=await this.request('/auth/v1/user',token);if(!/^[0-9a-f-]{36}$/i.test(user?.id||''))throw new AccessError('로그인 정보를 확인하세요.');
  const allowed=await this.request('/rest/v1/rpc/is_app_owner',token,{method:'POST',body:{}});if(allowed!==true)throw new AccessError('이 앱에 허용된 본인 계정이 아닙니다.',403);
  return {token,userId:user.id};
 }
 scoped(ctx,id){return '/rest/v1/trades?owner_id=eq.'+ctx.userId+(id?'&id=eq.'+encodeURIComponent(id):'');}
 async list(ctx){const rows=[];for(let offset=0;;offset+=1000){const page=await this.request(this.scoped(ctx)+'&select=id,payload&order=id&limit=1000&offset='+offset,ctx.token);rows.push(...page.map(r=>({id:r.id,...r.payload})));if(page.length<1000)break;}return rows.sort((a,b)=>b.exit.localeCompare(a.exit)||a.id.localeCompare(b.id));}
 async get(ctx,id){const rows=await this.request(this.scoped(ctx,id)+'&select=id,payload',ctx.token);return rows[0]?{id:rows[0].id,...rows[0].payload}:null;}
 async insert(ctx,id,trade){await this.request('/rest/v1/trades',ctx.token,{method:'POST',body:{id,owner_id:ctx.userId,payload:trade}});}
 async update(ctx,id,trade){await this.request(this.scoped(ctx,id),ctx.token,{method:'PATCH',body:{payload:trade}});}
 async updateIfUnchanged(ctx,id,trade,original){const {id:oldId,...payload}=original;const rows=await this.request(this.scoped(ctx,id)+'&payload=eq.'+encodeURIComponent(JSON.stringify(payload)),ctx.token,{method:'PATCH',body:{payload:trade},prefer:'return=representation'});return rows.length===1;}
 async delete(ctx,id){await this.request(this.scoped(ctx,id),ctx.token,{method:'DELETE'});}
 async import(ctx,rows){return this.request('/rest/v1/rpc/import_trades',ctx.token,{method:'POST',body:{records:rows.map(r=>({id:r.sourceId,payload:r.trade}))}});}
}
