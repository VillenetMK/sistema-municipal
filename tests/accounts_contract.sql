-- PostgreSQL LOCAL exclusivement: todas las filas ficticias se revierten.
begin;
create function pg_temp.reject_account(command text, expected text) returns void
language plpgsql security invoker as $$
begin
  execute command;
  raise exception 'TEST_UNEXPECTED_SUCCESS';
exception when others then
  if sqlerrm='TEST_UNEXPECTED_SUCCESS' or strpos(sqlerrm,expected)=0 then raise; end if;
end $$;
insert into auth.users(id,email) values
 ('bbbbbbbb-0000-4000-8000-000000000001','admin@example.test'),
 ('bbbbbbbb-0000-4000-8000-000000000002','reader@example.test');
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
 select id,'Operador local',case when email like 'admin%' then 'admin' else 'consulta' end,
 (select id from public.departments where code='MP'),true from auth.users where id::text like 'bbbbbbbb%';
set local role authenticated;
select set_config('request.jwt.claim.sub','bbbbbbbb-0000-4000-8000-000000000001',true);
do $$
declare payload jsonb; result jsonb;
begin
  payload:=jsonb_build_object('id','bbbbbbbb-0000-4000-8000-000000000011','email','invited@example.com',
    'display_name','Cuenta de prueba local','role','consulta','department_id',(select id from public.departments where code='MP'),
    'token',repeat('a',64),'reason','Alta de cuenta de prueba aislada');
  result:=public.admin_invitations('create',payload);
  if result ? 'token_hash' or result ? 'token' then raise exception 'Se expuso un secreto'; end if;
  if public.admin_invitations('create',payload)<>result then raise exception 'Reintento no idempotente'; end if;
  perform pg_temp.reject_account(format('select public.admin_invitations(%L,%L)','create',payload || '{"role":"admin"}'),'otra invitación');
  if jsonb_array_length(public.admin_invitations('list','{}'))<>1 then raise exception 'Listado inválido'; end if;
  perform pg_temp.reject_account('select * from private.staff_invitations','permission denied');
  perform set_config('request.jwt.claim.sub','bbbbbbbb-0000-4000-8000-000000000002',true);
  perform pg_temp.reject_account('select public.admin_invitations(''list'',''{}'')','administrador activo');
end $$;
reset role;
select pg_temp.reject_account($q$insert into auth.users(id,email,raw_user_meta_data) values
 ('bbbbbbbb-0000-4000-8000-000000000012','wrong@example.com',jsonb_build_object('municipal_invitation',repeat('a',64)))$q$,'no es válida');
-- El cliente intenta elevar su rol en metadata: solo manda el registro privado.
insert into auth.users(id,email,raw_user_meta_data) values
 ('bbbbbbbb-0000-4000-8000-000000000012','invited@example.com',jsonb_build_object('municipal_invitation',repeat('a',64),'role','admin'));
do $$
begin
 if (select role from public.staff_profiles where user_id='bbbbbbbb-0000-4000-8000-000000000012')<>'consulta' then raise exception 'Escalada por metadata'; end if;
 if (select raw_user_meta_data ? 'municipal_invitation' from auth.users where id='bbbbbbbb-0000-4000-8000-000000000012') then raise exception 'Código retenido en Auth'; end if;
 if not exists(select 1 from private.staff_invitations where claimed_by='bbbbbbbb-0000-4000-8000-000000000012') then raise exception 'Invitación sin consumir'; end if;
 if not exists(select 1 from public.admin_events where entity='staff_profiles' and record_id='bbbbbbbb-0000-4000-8000-000000000012') then raise exception 'Sin auditoría'; end if;
end $$;
select pg_temp.reject_account($q$insert into auth.users(id,email,raw_user_meta_data) values
 ('bbbbbbbb-0000-4000-8000-000000000013','invited@example.com',jsonb_build_object('municipal_invitation',repeat('a',64)))$q$,'no es válida');
insert into auth.users(id,email,raw_user_meta_data) values
 ('bbbbbbbb-0000-4000-8000-000000000014','uninvited@example.com','{"role":"admin"}');
do $$ begin
 if exists(select 1 from public.staff_profiles where user_id='bbbbbbbb-0000-4000-8000-000000000014') then raise exception 'Acceso sin invitación'; end if;
end $$;
set local role authenticated;
select set_config('request.jwt.claim.sub','bbbbbbbb-0000-4000-8000-000000000001',true);
select public.admin_invitations('create',jsonb_build_object('id','bbbbbbbb-0000-4000-8000-000000000021','email','revoked@example.com',
 'display_name','Cuenta revocable','role','gestor','department_id',(select id from public.departments where code='MP'),'token',repeat('b',64),'reason','Prueba de revocación local'));
select public.admin_invitations('revoke','{"id":"bbbbbbbb-0000-4000-8000-000000000021","reason":"Revocación de prueba local"}');
reset role;
select pg_temp.reject_account($q$insert into auth.users(id,email,raw_user_meta_data) values
 ('bbbbbbbb-0000-4000-8000-000000000022','revoked@example.com',jsonb_build_object('municipal_invitation',repeat('b',64)))$q$,'no es válida');
update private.staff_invitations set revoked_at=null,expires_at=now()-interval '1 minute' where id='bbbbbbbb-0000-4000-8000-000000000021';
select pg_temp.reject_account($q$insert into auth.users(id,email,raw_user_meta_data) values
 ('bbbbbbbb-0000-4000-8000-000000000022','revoked@example.com',jsonb_build_object('municipal_invitation',repeat('b',64)))$q$,'no es válida');
update private.staff_invitations set expires_at=now()+interval '1 hour' where id='bbbbbbbb-0000-4000-8000-000000000021';
update public.staff_profiles set is_active=false where user_id='bbbbbbbb-0000-4000-8000-000000000001';
select pg_temp.reject_account($q$insert into auth.users(id,email,raw_user_meta_data) values
 ('bbbbbbbb-0000-4000-8000-000000000022','revoked@example.com',jsonb_build_object('municipal_invitation',repeat('b',64)))$q$,'ya no está autorizado');
set local role anon;
select pg_temp.reject_account('select public.admin_invitations(''list'',''{}'')','permission denied');
reset role;
rollback;
