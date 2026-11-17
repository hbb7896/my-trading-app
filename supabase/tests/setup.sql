create role anon nologin;
create role authenticated nologin;
create schema auth;
create table auth.users(id uuid primary key,email text);
create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
grant usage on schema auth to anon,authenticated;
grant execute on function auth.uid() to anon,authenticated;
insert into auth.users values('11111111-1111-4111-8111-111111111111','owner@example.test'),('22222222-2222-4222-8222-222222222222','outsider@example.test');
