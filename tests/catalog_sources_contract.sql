-- Solo base aislada: fuente, vigencia y conservación del catálogo histórico.
begin;
create function pg_temp.catalog_reject(command text, expected text) returns void
language plpgsql security invoker as $$
begin execute command; raise exception 'TEST_UNEXPECTED_SUCCESS';
exception when others then
  if sqlerrm='TEST_UNEXPECTED_SUCCESS' or strpos(sqlerrm,expected)=0 then raise; end if;
end $$;
insert into auth.users(id) values ('cccccccc-1111-4000-8000-000000000001');
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
select 'cccccccc-1111-4000-8000-000000000001','Administrador de catálogo','admin',id,true
from public.departments where code='MP';
set local role authenticated;
select set_config('request.jwt.claim.sub','cccccccc-1111-4000-8000-000000000001',true);
do $$ declare draft jsonb; proc jsonb; payload jsonb; target jsonb;
  today date:=(now() at time zone 'America/Lima')::date;
begin
  draft:=jsonb_build_object('id',gen_random_uuid(),'code','VIGENCIA','name','Ficha local de vigencia',
    'department_id',(select id from public.departments where code='MP'),'is_active',true,'is_official',true,
    'requirements','','legal_basis','Referencia ficticia exclusiva para pruebas locales.');
  perform pg_temp.catalog_reject(format('select public.admin_save_record(%L,%L,0,%L)',
    'procedures',draft,'Intento sin fuente verificable.'),'fuente verificable');
  draft:=draft||jsonb_build_object('source_url','https://example.test/ficha','valid_from',today,'valid_until',today-1);
  perform pg_temp.catalog_reject(format('select public.admin_save_record(%L,%L,0,%L)',
    'procedures',draft,'Intento con intervalo invertido.'),'fin de vigencia');
  proc:=public.admin_save_record('procedures',draft||jsonb_build_object('valid_from',today-2),0,'Alta de ficha vencida para ensayo.');
  payload:=jsonb_build_object('request_id',gen_random_uuid(),'department_id',proc->>'department_id',
    'procedure_id',proc->>'id','document_type','DNI','document_number','00000088',
    'applicant_name','Solicitante ficticio de catálogo','email','','phone','',
    'title','Solicitud ficticia de vigencia','description','Registro exclusivo del contrato de catálogo.',
    'priority','normal','channel','presencial');
  perform pg_temp.catalog_reject(format('select public.register_case(%L)',payload),'vigente');
  proc:=public.admin_save_record('procedures',proc||jsonb_build_object('valid_from',today+1,'valid_until',null),1,
    'Adelantar vigencia para probar rechazo.');
  perform pg_temp.catalog_reject(format('select public.register_case(%L)',payload),'vigente');
  proc:=public.admin_save_record('procedures',proc||jsonb_build_object('valid_from',today,'valid_until',today),2,
    'Habilitar ficha vigente durante hoy.');
  target:=public.register_case(payload);
  if target->'procedure_snapshot'->>'source_url'<>'https://example.test/ficha' then
    raise exception 'Fuente no conservada en el expediente'; end if;
  proc:=public.admin_save_record('procedures',(proc-'source_url'-'valid_from'-'valid_until')||'{"name":"Nombre actualizado"}',3,
    'Actualizar desde cliente anterior sin borrar vigencia.');
  if proc->>'source_url'<>'https://example.test/ficha' or (proc->>'valid_until')::date<>today then
    raise exception 'Cliente anterior borró la fuente o vigencia'; end if;
  if public.register_case(payload)<>target then raise exception 'Reintento perdió la ficha original'; end if;
end $$;
rollback;
