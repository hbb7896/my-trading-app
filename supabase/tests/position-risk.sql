-- Local/CI database only. setup.sql and both migrations must already be applied.
reset role;
insert into auth.users values('33333333-3333-4333-8333-333333333333','risk-owner@example.test'),('44444444-4444-4444-8444-444444444444','risk-outsider@example.test') on conflict do nothing;
-- Reuse an existing CI app owner, otherwise register the dedicated test owner.
insert into private.app_owner(user_id) select '33333333-3333-4333-8333-333333333333' where not exists(select 1 from private.app_owner);
select set_config('request.jwt.claim.sub',(select user_id::text from private.app_owner limit 1),false);
set role authenticated;
do $$
declare c jsonb:='{"id":"sql-risk","ticker":"test","code":"","version":1,"events":[{"id":"buy1","type":"buy","price":"100","quantity":"10","stop":"90","at":"2026-11-16T09:00:00Z"}]}'; n jsonb;
begin
 if not public.commit_position_cycle(0,c,null) then raise exception 'create failed';end if;
 if public.commit_position_cycle(0,c,null) then raise exception 'stale revision accepted';end if;
 begin
  update public.position_cycles set payload=jsonb_set(payload,'{events,0,stop}','"99"') where id='sql-risk';
  raise exception 'initial stop mutation allowed';
 exception when raise_exception then if sqlerrm='initial stop mutation allowed' then raise;end if;end;
 begin
  update public.position_cycles set owner_id='44444444-4444-4444-8444-444444444444' where id='sql-risk';
  raise exception 'owner mutation allowed';
 exception when others then if sqlerrm='owner mutation allowed' then raise;end if;end;
 n:=jsonb_set(jsonb_set(c,'{version}','2'),'{events}',(c->'events')||'[{"id":"sell1","type":"sell","price":"120","allocations":[{"lotId":"buy1","quantity":"10"}],"at":"2026-11-16T10:00:00Z"}]');
 begin
  perform public.commit_position_cycle(1,n,'{"risk_cycle_id":"wrong"}');raise exception 'invalid projection accepted';
 exception when raise_exception then if sqlerrm='invalid projection accepted' then raise;end if;end;
 if (select payload->>'version' from public.position_cycles where id='sql-risk')<>'1' then raise exception 'failed projection not rolled back';end if;
 if not public.commit_position_cycle(1,n,'{"risk_cycle_id":"sql-risk","ticker":"test","code":"","entry":"2026-11-16","exit":"2026-11-16","buy":1000,"sell":1200,"memo":"","initial_r":100,"final_r":2}') then raise exception 'close failed';end if;
 if (select count(*) from public.trades where id='RISK_sql-risk')<>1 then raise exception 'projection missing';end if;
end $$;
set request.jwt.claim.sub='44444444-4444-4444-8444-444444444444';
do $$begin
 if (select count(*) from public.position_cycles)<>0 then raise exception 'outsider read';end if;
 begin perform public.commit_position_cycle(0,'{}',null);raise exception 'outsider write';exception when others then if sqlerrm='outsider write' then raise;end if;end;
 if (select count(*) from public.position_risk_settings)<>0 then raise exception 'outsider settings';end if;
end $$;
reset role;
set role anon;
do $$begin
 begin perform count(*) from public.position_cycles;raise exception 'anon read';exception when insufficient_privilege then null;end;
 begin perform public.commit_position_cycle(0,'{}',null);raise exception 'anon rpc';exception when insufficient_privilege then null;end;
end $$;
reset role;
