-- Exclusivamente en PostgreSQL LOCAL. Todo se revierte, incluidas las identidades ficticias.
begin;
create function pg_temp.expect_rejection(command text, expected text) returns void
language plpgsql security invoker as $$
begin
  execute command;
  raise exception 'TEST_UNEXPECTED_SUCCESS';
exception when others then
  if sqlerrm = 'TEST_UNEXPECTED_SUCCESS' or strpos(sqlerrm,expected)=0 then raise; end if;
end $$;
insert into auth.users(id) select ('aaaaaaaa-0000-4000-8000-' || lpad(i::text,12,'0'))::uuid from generate_series(1,6) i;
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
 select ('aaaaaaaa-0000-4000-8000-' || lpad(i::text,12,'0'))::uuid,
   'Persona de prueba ' || i,case i when 1 then 'admin' when 2 then 'admin' when 3 then 'gestor'
     when 4 then 'mesa_partes' when 5 then 'consulta' else 'admin' end,
   (select id from public.departments where code='MP'),i<>6 from generate_series(1,6) i;

set local role authenticated;
select set_config('request.jwt.claim.sub','aaaaaaaa-0000-4000-8000-000000000001',true);
do $$
declare area jsonb; proc jsonb; result jsonb; target jsonb; member jsonb; count_events int;
begin
  if jsonb_array_length(public.admin_list_records('departments','GM',0)) <> 1 then raise exception 'Búsqueda incorrecta'; end if;
  perform pg_temp.expect_rejection($q$select public.admin_list_records('departments','',-1)$q$,'página inválida');
  perform pg_temp.expect_rejection($q$select public.admin_list_records('auth.users','',0)$q$,'Sección');
  area := public.admin_save_record('departments',jsonb_build_object('id',gen_random_uuid(),'code','TESTQA',
    'name','Área de prueba','is_active',true,'unit_type','referencia','source_url',null),0,'Alta de área para prueba local.');
  if (area->>'version')::int <> 1 then raise exception 'Versión inicial incorrecta'; end if;
  perform set_config('test.admin_area',area->>'id',true);
  if not exists(select 1 from public.admin_events where record_id=(area->>'id')::uuid and before_data is null
    and actor_id=auth.uid() and after_data=area) then raise exception 'Falta auditoría del alta'; end if;
  result := public.admin_save_record('departments',area || '{"name":"Área de prueba actualizada"}',1,'Actualizar nombre del área local.');
  if (result->>'version')::int<>2 then raise exception 'Versión no incrementada'; end if;
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,1,%L)',
    'departments',area,'Actualización con versión antigua.'),'Otro usuario');
  area := result;
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,0,%L)',
    'departments',area || jsonb_build_object('id',gen_random_uuid()),'Intento de duplicar código del área.'),'código ya existe');
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,null,%L)',
    'departments',area,'Edición sin control de versión.'),'versión');
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,2,%L)',
    'departments',area || '{"source_url":"javascript:alert(1)"}','Enlace inválido de prueba local.'),'HTTPS');
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,2,%L)',
    'departments',area,'corto'),'motivo');

  proc := public.admin_save_record('procedures',jsonb_build_object('id',gen_random_uuid(),'code','TESTPROC',
    'name','Trámite de prueba','requirements','','is_active',true,'department_id',area->>'id',
    'is_official',false,'fee_pen',0,'deadline_days',null),0,'Alta de ficha de referencia local.');
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,1,%L)',
    'procedures',proc || '{"is_official":true,"legal_basis":null}','Ficha oficial sin sustento.'),'sustento');
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,1,%L)',
    'procedures',proc || '{"fee_pen":"NaN"}','Importe inválido para prueba.'),'importe');
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,1,%L)',
    'procedures',proc || '{"deadline_days":1.5}','Plazo fraccionario para prueba.'),'entero');
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,2,%L)',
    'departments',area || '{"is_active":false}','Desactivar área con trámite activo.'),'trámites activos');
  proc := public.admin_save_record('procedures',proc || '{"is_active":false}',1,'Desactivar ficha para prueba local.');

  target := public.register_case(jsonb_build_object('request_id',gen_random_uuid(),'department_id',area->>'id',
    'document_type','DNI','document_number','00000001','applicant_name','Solicitante ficticio','email','','phone','',
    'title','Solicitud local de prueba','description','Texto de solicitud exclusivo para pruebas locales.',
    'priority','normal','channel','presencial','due_on',null));
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,2,%L)',
    'departments',area || '{"is_active":false}','Desactivar área con expediente abierto.'),'sin archivar');
  target := public.advance_case((target->>'id')::uuid,1,'en_revision',(area->>'id')::uuid,'Revisión local del expediente.');
  target := public.advance_case((target->>'id')::uuid,2,'atendido',(area->>'id')::uuid,'Atención local del expediente.');
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,2,%L)',
    'departments',area || '{"is_active":false}','Desactivar área antes del archivo.'),'sin archivar');
  perform public.advance_case((target->>'id')::uuid,3,'archivado',(area->>'id')::uuid,'Archivo local del expediente.');
  area := public.admin_save_record('departments',area || '{"is_active":false}',2,'Desactivar área sin trabajo pendiente.');
  if (select count(*) from public.cases)<>1 then raise exception 'Se perdió el historial del expediente'; end if;
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,2,%L)',
    'procedures',proc || '{"is_active":true}','Activar ficha en área inactiva.'),'área activa');
  area := public.admin_save_record('departments',area || '{"is_active":true}',3,'Reactivar área para continuar prueba.');

  select to_jsonb(s) into member from public.staff_profiles s where user_id='aaaaaaaa-0000-4000-8000-000000000003';
  member := public.admin_save_record('staff_profiles',member || jsonb_build_object('department_id',area->>'id'),1,'Reasignación de gestor de prueba.');
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,4,%L)',
    'departments',area || '{"is_active":false}','Desactivar área con personal activo.'),'personal activo');
  member := public.admin_save_record('staff_profiles',member || '{"is_active":false}',2,'Desactivar gestor de prueba local.');
  perform set_config('test.admin_member',member::text,true);
  select to_jsonb(s) into member from public.staff_profiles s where user_id=auth.uid();
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,1,%L)',
    'staff_profiles',member || '{"is_active":false}','Intento de desactivar cuenta propia.'),'propia cuenta');
  perform pg_temp.expect_rejection(format('select public.admin_save_record(%L,%L,1,%L)',
    'staff_profiles',member || '{"role":"consulta"}','Intento de retirar rol propio.'),'propia cuenta');
  select to_jsonb(s) into member from public.staff_profiles s where user_id='aaaaaaaa-0000-4000-8000-000000000002';
  perform public.admin_save_record('staff_profiles',member || '{"role":"consulta"}',1,'Cambio autorizado de otro administrador.');

  select count(*) into count_events from public.admin_events;
  if count_events<>9 then raise exception 'Se esperaban 9 cambios, hay %',count_events; end if;
  perform pg_temp.expect_rejection('update public.departments set is_active=false','permission denied');
  perform pg_temp.expect_rejection('update public.staff_profiles set role=''admin''','permission denied');
  perform pg_temp.expect_rejection('delete from public.admin_events','permission denied');
  perform pg_temp.expect_rejection('update public.admin_events set reason=''alterado''','permission denied');
end $$;

-- Rol retirado, gestor desactivado, mesa de partes, consulta y administrador inactivo.
do $$ declare i int; member jsonb; begin
  for i in 2..6 loop
    perform set_config('request.jwt.claim.sub','aaaaaaaa-0000-4000-8000-' || lpad(i::text,12,'0'),true);
    perform pg_temp.expect_rejection('select public.admin_list_records(''staff_profiles'')','administrador activo');
    perform pg_temp.expect_rejection('select public.admin_save_record(''staff_profiles'',''{}'',0,''Intento no autorizado'')','administrador activo');
    if (select count(*) from public.admin_events)<>0 then raise exception 'Fuga del historial de administración'; end if;
  end loop;
end $$;
reset role;
set local role anon;
select set_config('request.jwt.claim.sub','',true);
select pg_temp.expect_rejection('select public.admin_list_records(''departments'')','permission denied');
select pg_temp.expect_rejection('select public.admin_save_record(''departments'',''{}'',0,''Intento anónimo'')','permission denied');
select pg_temp.expect_rejection('select * from public.admin_events','permission denied');
reset role;
rollback;
