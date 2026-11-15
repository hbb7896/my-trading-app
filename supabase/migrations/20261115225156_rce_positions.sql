-- Additive: existing trades and owner policy are not rewritten.
create table public.position_cycles (
 owner_id uuid not null references auth.users(id),
 id text not null check(id ~ '^[a-zA-Z0-9_-]{1,100}$'),
 payload jsonb not null check(coalesce(
  jsonb_typeof(payload)='object' and payload ?& array['id','ticker','code','version','events']
  and jsonb_typeof(payload->'id')='string' and jsonb_typeof(payload->'ticker')='string'
  and length(payload->>'ticker') between 1 and 100 and jsonb_typeof(payload->'code')='string'
  and (payload->>'version') ~ '^[1-9][0-9]{0,3}$'
  and jsonb_typeof(payload->'events')='array' and jsonb_array_length(payload->'events') between 1 and 2000
  and octet_length(payload::text)<=1048576,false)),
 primary key(owner_id,id)
);
create table public.position_risk_settings (
 owner_id uuid primary key references auth.users(id),
 payload jsonb not null check(jsonb_typeof(payload)='object' and octet_length(payload::text)<=8192)
);
alter table public.position_cycles enable row level security;
alter table public.position_risk_settings enable row level security;
create policy owner_cycles on public.position_cycles for all to authenticated
 using(owner_id=(select auth.uid()) and (select public.is_app_owner()))
 with check(owner_id=(select auth.uid()) and (select public.is_app_owner()));
create policy owner_risk_settings on public.position_risk_settings for all to authenticated
 using(owner_id=(select auth.uid()) and (select public.is_app_owner()))
 with check(owner_id=(select auth.uid()) and (select public.is_app_owner()));
revoke all on public.position_cycles,public.position_risk_settings from public,anon;
grant select,insert,update on public.position_cycles,public.position_risk_settings to authenticated;

create function private.guard_position_history() returns trigger language plpgsql set search_path='' as $$
begin
 if new.payload->>'id'<>new.id then raise exception 'cycle id mismatch'; end if;
 if tg_op='UPDATE' then
  if new.owner_id<>old.owner_id or new.id<>old.id or new.payload->'ticker'<>old.payload->'ticker' or new.payload->'code'<>old.payload->'code'
   or (new.payload->>'version')::integer<>(old.payload->>'version')::integer+1
   or jsonb_array_length(new.payload->'events')<>jsonb_array_length(old.payload->'events')+1
   or exists(select 1 from jsonb_array_elements(old.payload->'events') with ordinality e(v,n) where new.payload->'events'->((e.n-1)::integer) is distinct from e.v)
  then raise exception 'position history is append only'; end if;
 else
  if (new.payload->>'version')::integer<>1 or jsonb_array_length(new.payload->'events')<>1 or new.payload->'events'->0->>'type'<>'buy' then raise exception 'first buy required'; end if;
 end if;
 return new;
end $$;
create trigger guard_position_history before insert or update on public.position_cycles for each row execute function private.guard_position_history();
revoke all on function private.guard_position_history() from public,anon,authenticated;

-- One transaction: optimistic revision check, append event, and completed-trade projection.
-- Invoker security retains the caller's existing owner RLS on both tables.
create function public.commit_position_cycle(expected_version integer,next_cycle jsonb,closed_trade jsonb default null)
returns boolean language plpgsql security invoker set search_path='' as $$
declare previous jsonb; cycle_id text:=next_cycle->>'id';
begin
 if auth.uid() is null or not public.is_app_owner() then raise exception 'not authorized'; end if;
 perform pg_advisory_xact_lock(hashtextextended(auth.uid()::text||':'||cycle_id,0));
 select payload into previous from public.position_cycles where owner_id=auth.uid() and id=cycle_id for update;
 if coalesce((previous->>'version')::integer,0)<>expected_version then return false; end if;
 if previous is null then insert into public.position_cycles values(auth.uid(),cycle_id,next_cycle);
 else update public.position_cycles set payload=next_cycle where owner_id=auth.uid() and id=cycle_id; end if;
 if closed_trade is not null then
  if closed_trade->>'risk_cycle_id' is distinct from cycle_id then raise exception 'projection mismatch'; end if;
  insert into public.trades(owner_id,id,payload) values(auth.uid(),'RISK_'||cycle_id,closed_trade);
 end if;
 return true;
end $$;
revoke all on function public.commit_position_cycle(integer,jsonb,jsonb) from public,anon;
grant execute on function public.commit_position_cycle(integer,jsonb,jsonb) to authenticated;
