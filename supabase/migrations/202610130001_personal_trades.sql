begin;
create schema if not exists private;
revoke all on schema private from public,anon,authenticated;
create table private.app_owner (
 user_id uuid primary key references auth.users(id) on delete cascade,
 created_at timestamptz not null default now()
);
revoke all on private.app_owner from public,anon,authenticated;
create function public.is_app_owner() returns boolean
language sql stable security definer set search_path=''
as $$select exists(select 1 from private.app_owner where user_id=(select auth.uid()))$$;
revoke all on function public.is_app_owner() from public,anon;
grant execute on function public.is_app_owner() to authenticated;

create function private.valid_trade(p jsonb) returns boolean
language plpgsql immutable set search_path='' as $$
declare buy_amount numeric; sell_amount numeric; entry_date date; exit_date date;
begin
 if jsonb_typeof(p) is distinct from 'object' or not(p ?& array['ticker','code','entry','exit','buy','sell','memo']) then return false;end if;
 if jsonb_typeof(p->'ticker') is distinct from 'string' or length(btrim(p->>'ticker')) not between 1 and 100 then return false;end if;
 if jsonb_typeof(p->'code') is distinct from 'string' or ((p->>'code')<>'' and (p->>'code')!~'^[0-9]{6}$') then return false;end if;
 if jsonb_typeof(p->'entry') is distinct from 'string' or jsonb_typeof(p->'exit') is distinct from 'string' or (p->>'exit')!~'^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then return false;end if;
 exit_date:=(p->>'exit')::date;if to_char(exit_date,'YYYY-MM-DD')<>p->>'exit' then return false;end if;
 if (p->>'entry')<>'' then
  if (p->>'entry')!~'^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then return false;end if;
  entry_date:=(p->>'entry')::date;if to_char(entry_date,'YYYY-MM-DD')<>p->>'entry' or entry_date>exit_date then return false;end if;
 end if;
 if jsonb_typeof(p->'buy') is distinct from 'number' or jsonb_typeof(p->'sell') is distinct from 'number' then return false;end if;
 buy_amount:=(p->>'buy')::numeric;sell_amount:=(p->>'sell')::numeric;
 if buy_amount<=0 or buy_amount>1e15 or sell_amount<0 or sell_amount>1e15 then return false;end if;
 if jsonb_typeof(p->'memo') is distinct from 'string' or length(p->>'memo')>10000 then return false;end if;
 return true;
exception when others then return false;
end $$;
create table public.trades (
 owner_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
 id text not null check(length(id) between 1 and 100),
 payload jsonb not null check(private.valid_trade(payload)) check(octet_length(payload::text)<=65536),
 created_at timestamptz not null default now(),
 primary key(owner_id,id)
);
alter table public.trades enable row level security;
revoke all on public.trades from public,anon;
grant select,insert,update,delete on public.trades to authenticated;
create policy owner_read on public.trades for select to authenticated using(owner_id=(select auth.uid()) and (select public.is_app_owner()));
create policy owner_insert on public.trades for insert to authenticated with check(owner_id=(select auth.uid()) and (select public.is_app_owner()));
create policy owner_update on public.trades for update to authenticated using(owner_id=(select auth.uid()) and (select public.is_app_owner())) with check(owner_id=(select auth.uid()) and (select public.is_app_owner()));
create policy owner_delete on public.trades for delete to authenticated using(owner_id=(select auth.uid()) and (select public.is_app_owner()));
create function public.import_trades(records jsonb) returns jsonb
language plpgsql security invoker set search_path='' as $$
declare import_record jsonb; inserted_count integer:=0; affected integer;
begin
 if not public.is_app_owner() then raise exception 'Owner access required' using errcode='42501';end if;
 if jsonb_typeof(records)<>'array' or jsonb_array_length(records) not between 1 and 5000 then raise exception 'Invalid import';end if;
 for import_record in select value from jsonb_array_elements(records) loop
  insert into public.trades(owner_id,id,payload) values(auth.uid(),import_record->>'id',import_record->'payload') on conflict(owner_id,id) do nothing;
  get diagnostics affected=row_count;inserted_count:=inserted_count+affected;
 end loop;
 return jsonb_build_object('inserted',inserted_count,'skipped',jsonb_array_length(records)-inserted_count);
end $$;
revoke all on function public.import_trades(jsonb) from public,anon;
grant execute on function public.import_trades(jsonb) to authenticated;
commit;
