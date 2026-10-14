insert into private.app_owner(user_id) values('11111111-1111-4111-8111-111111111111');
set role authenticated;
set request.jwt.claim.sub='11111111-1111-4111-8111-111111111111';
insert into public.trades(id,payload) values('test','{"ticker":"test","code":"005930","entry":"2026-01-01","exit":"2026-01-02","buy":100,"sell":110,"memo":""}');
do $$begin
 if not public.is_app_owner() or (select count(*) from public.trades)<>1 then raise exception 'Owner read failed';end if;
 begin
 insert into public.trades(owner_id,id,payload) values('22222222-2222-4222-8222-222222222222','bad','{"ticker":"test","code":"","entry":"","exit":"2026-01-02","buy":100,"sell":110,"memo":""}');
 raise exception 'Cross-owner insert allowed';
 exception when insufficient_privilege then null;end;
 begin
 insert into public.trades(id,payload) values('null-fields','{"ticker":null,"code":null,"entry":null,"exit":null,"buy":null,"sell":null,"memo":null}');
 raise exception 'Null data allowed';exception when check_violation then null;end;
end $$;
select public.import_trades('[{"id":"imported","payload":{"ticker":"test","code":"","entry":"","exit":"2026-01-02","buy":100,"sell":90,"memo":""}}]');
do $$begin if (public.import_trades('[{"id":"imported","payload":{"ticker":"test","code":"","entry":"","exit":"2026-01-02","buy":100,"sell":90,"memo":""}}]')->>'inserted')::int<>0 then raise exception 'Duplicate import';end if;end $$;
set request.jwt.claim.sub='22222222-2222-4222-8222-222222222222';
do $$begin
 if public.is_app_owner() or (select count(*) from public.trades)<>0 then raise exception 'Outsider read allowed';end if;
 begin
 insert into public.trades(id,payload) values('bad','{"ticker":"test","code":"","entry":"","exit":"2026-01-02","buy":100,"sell":110,"memo":""}');
 raise exception 'Outsider write allowed';exception when insufficient_privilege then null;end;
 update public.trades set payload='{}';if found then raise exception 'Outsider update allowed';end if;
 delete from public.trades;if found then raise exception 'Outsider delete allowed';end if;
 begin
 perform public.import_trades('[]');raise exception 'Outsider import allowed';exception when insufficient_privilege then null;end;
end $$;
reset role;
set role anon;
do $$begin
 begin perform count(*) from public.trades;raise exception 'Anonymous read allowed';exception when insufficient_privilege then null;end;
end $$;
reset role;
