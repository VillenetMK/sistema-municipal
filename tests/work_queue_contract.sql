-- Solo PostgreSQL LOCAL. Identidades y expedientes ficticios dentro de rollback.
begin;
create function pg_temp.work_reject(command text, expected text) returns void
language plpgsql security invoker as $$
begin execute command; raise exception 'TEST_UNEXPECTED_SUCCESS';
exception when others then
  if sqlerrm='TEST_UNEXPECTED_SUCCESS' or strpos(sqlerrm,expected)=0 then raise; end if;
end $$;
insert into auth.users(id) select ('aaaaaaaa-0000-4000-8000-' || lpad(i::text,12,'0'))::uuid from generate_series(1,6) i;
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
 select ('aaaaaaaa-0000-4000-8000-' || lpad(i::text,12,'0'))::uuid,'Persona de prueba ' || i,
   case i when 1 then 'admin' when 4 then 'consulta' when 6 then 'mesa_partes' else 'gestor' end,
   (select id from public.departments where code=case i when 3 then 'GM' else 'MP' end),i<>5
 from generate_series(1,6) i;
insert into public.procedures(id,code,name,requirements,department_id,deadline_days)
 select 'bbbbbbbb-0000-4000-8000-000000000001','PRUEBA','Ficha de prueba','Requisitos originales',id,5
 from public.departments where code='MP';
set local role authenticated;
select set_config('request.jwt.claim.sub','aaaaaaaa-0000-4000-8000-000000000001',true);
do $$
declare payload jsonb; target jsonb; repeated jsonb; ficha jsonb; member jsonb; change jsonb; before_count int;
  proc_id uuid:='bbbbbbbb-0000-4000-8000-000000000001';
  worker uuid:='aaaaaaaa-0000-4000-8000-000000000002';
begin
  payload:=jsonb_build_object('request_id',gen_random_uuid(),'department_id',(select id from public.departments where code='MP'),
    'document_type','DNI','document_number','00000001','applicant_name','Solicitante de prueba','email','','phone','',
    'title','Expediente local de organización','description','Expediente exclusivo para comprobar organización del trabajo.',
    'priority','normal','channel','presencial','due_on',null,'procedure_id',proc_id,'assigned_to',worker,
    'procedure_snapshot',jsonb_build_object('name','Ficha falsificada por el cliente'));
  target:=public.register_case(payload);
  repeated:=public.register_case(payload);
  if target<>repeated or (select count(*) from public.cases)<>1 then raise exception 'Falló idempotencia con responsable'; end if;
  if target->'procedure_snapshot'->>'name'<>'Ficha de prueba' then raise exception 'Snapshot falsificable'; end if;
  if target->>'due_on' is not null then raise exception 'Plazo legal aplicado sin autorización'; end if;
  if target->>'assigned_to'<>worker::text then raise exception 'Asignación perdida al registrar'; end if;
  if not exists(select 1 from public.case_events where case_id=(target->>'id')::uuid
    and work_after->>'assignee_name'='Persona de prueba 2') then raise exception 'Alta sin historial de responsable'; end if;
  perform pg_temp.work_reject(format('select public.register_case(%L)',payload || '{"assigned_to":null}'),'otros datos');
  perform set_config('test.work_case',target->>'id',true);
  perform set_config('test.work_area',target->>'department_id',true);
  foreach worker in array array['aaaaaaaa-0000-4000-8000-000000000003'::uuid,
    'aaaaaaaa-0000-4000-8000-000000000004'::uuid,'aaaaaaaa-0000-4000-8000-000000000005'::uuid] loop
    perform pg_temp.work_reject(format('select public.register_case(%L)',payload || jsonb_build_object('request_id',gen_random_uuid(),'assigned_to',worker)),
      'responsable debe ser');
  end loop;
  if (select count(*) from public.cases)<>1 then raise exception 'Alta inválida dejó expediente parcial'; end if;
  select to_jsonb(p) into ficha from public.procedures p where id=proc_id;
  ficha:=public.admin_save_record('procedures',ficha || '{"name":"Nombre nuevo del catálogo","requirements":"Requisitos nuevos","is_active":false}',1,
    'Cambio local para probar la conservación de la ficha.');
  if (select procedure_snapshot->>'name' from public.cases where id=(target->>'id')::uuid)<>'Ficha de prueba' then
    raise exception 'Cambiar catálogo modificó ficha histórica'; end if;
  perform pg_temp.work_reject(format('select public.register_case(%L)',payload || jsonb_build_object('request_id',gen_random_uuid())),
    'trámite activo');
  repeated:=public.register_case(payload);
  if repeated<>target then raise exception 'Reintento dejó de funcionar tras desactivar ficha'; end if;

  select to_jsonb(s) into member from public.staff_profiles s where user_id='aaaaaaaa-0000-4000-8000-000000000002';
  perform pg_temp.work_reject(format('select public.admin_save_record(%L,%L,1,%L)',
    'staff_profiles',member || '{"is_active":false}','Desactivar responsable con trabajo pendiente.'),'Reasigna o libera');
  perform pg_temp.work_reject(format('select public.admin_save_record(%L,%L,1,%L)',
    'staff_profiles',member || '{"role":"consulta"}','Retirar permiso de atención de responsable.'),'Reasigna o libera');
  perform pg_temp.work_reject(format('select public.admin_save_record(%L,%L,1,%L)',
    'staff_profiles',member || jsonb_build_object('department_id',(select id from public.departments where code='GM')),
    'Cambiar de área al responsable con pendientes.'),'Reasigna o libera');

  select count(*) into before_count from public.case_events;
  target:=public.set_case_work((target->>'id')::uuid,1,proc_id,(target->>'assigned_to')::uuid,'urgente','2026-10-01',
    'Priorizar la atención con una fecha objetivo interna.');
  if target->'procedure_snapshot'->>'requirements'<>'Requisitos originales' then raise exception 'Se perdió la versión de la ficha'; end if;
  if (select count(*) from public.case_events)<>before_count+1 then raise exception 'Organización sin historial'; end if;
  select work_before into change from public.case_events where action='organización' order by id desc limit 1;
  if change->>'priority'<>'normal' then raise exception 'Prioridad anterior incorrecta'; end if;
  perform pg_temp.work_reject(format('select public.advance_case(%L,1,%L,%L,%L)',
    target->>'id','en_revision',target->>'department_id','Intento desde una pantalla obsoleta.'),'Otro usuario');
  perform pg_temp.work_reject(format('select public.set_case_work(%L,1,%L,null,%L,null,%L)',
    target->>'id',proc_id,'normal','Intento de organizar con versión anterior.'),'Otro usuario');
  perform pg_temp.work_reject(format('select public.set_case_work(%L,2,%L,%L,%L,%L,%L)',
    target->>'id',proc_id,target->>'assigned_to','urgente','2026-10-01','Guardado sin cambios en la organización.'),'Modifica');
  perform pg_temp.work_reject('update public.cases set assigned_to=null','permission denied');
end $$;

-- Consulta y otra área no pueden cambiar organización, aunque conozcan el UUID.
do $$ declare actor text; begin
  foreach actor in array array['aaaaaaaa-0000-4000-8000-000000000003','aaaaaaaa-0000-4000-8000-000000000004','aaaaaaaa-0000-4000-8000-000000000005'] loop
    perform set_config('request.jwt.claim.sub',actor,true);
    perform pg_temp.work_reject(format('select public.set_case_work(%L,2,%L,null,%L,null,%L)',current_setting('test.work_case'),
      'bbbbbbbb-0000-4000-8000-000000000001','normal','Cambio que no pertenece a este perfil.'),
      case when actor like '%000003' then 'no está disponible' else 'no puede organizar' end);
  end loop;
end $$;

-- El gestor puede organizar su área; la derivación libera al responsable original.
select set_config('request.jwt.claim.sub','aaaaaaaa-0000-4000-8000-000000000002',true);
do $$ declare target jsonb; begin
  target:=public.advance_case(current_setting('test.work_case')::uuid,2,'en_revision',current_setting('test.work_area')::uuid,'Comenzar revisión del expediente local.');
  if target->>'assigned_to'<>auth.uid()::text then raise exception 'Cambio de estado retiró al responsable'; end if;
  target:=public.advance_case((target->>'id')::uuid,3,'en_revision',(select id from public.departments where code='GM'),'Derivación a la gerencia para continuar atención.');
  if target->>'assigned_to' is not null then raise exception 'Se conservó responsable de otra área'; end if;
  if (select count(*) from public.cases)<>0 then raise exception 'El gestor conserva acceso después de derivar'; end if;
end $$;
select set_config('request.jwt.claim.sub','aaaaaaaa-0000-4000-8000-000000000003',true);
do $$ declare target jsonb; begin
  if (select count(*) from public.cases)<>1 then raise exception 'El área nueva no recibió el expediente'; end if;
  if not exists(select 1 from public.case_events where action='derivación' and work_before->>'assignee_name'='Persona de prueba 2'
    and work_after->>'assigned_to' is null) then raise exception 'Derivación sin historial de asignación'; end if;
  target:=public.set_case_work(current_setting('test.work_case')::uuid,4,'bbbbbbbb-0000-4000-8000-000000000001',auth.uid(),
    'alta',null,'Tomar responsabilidad en el área de destino.');
  if target->>'assigned_to'<>auth.uid()::text then raise exception 'No se asignó al gestor de destino'; end if;
  target:=public.advance_case((target->>'id')::uuid,5,'atendido',(target->>'department_id')::uuid,'Atención completada para la prueba local.');
  perform pg_temp.work_reject(format('select public.set_case_work(%L,6,%L,null,%L,null,%L)',target->>'id',
    'bbbbbbbb-0000-4000-8000-000000000001','normal','Intentar editar un expediente cerrado.'),'cerrado');
end $$;
reset role;
set local role anon;
select set_config('request.jwt.claim.sub','',true);
select pg_temp.work_reject('select public.set_case_work(null,1,null,null,''normal'',null,''Intento anónimo de prueba.'')','permission denied');
reset role;
rollback;
