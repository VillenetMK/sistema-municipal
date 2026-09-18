-- Solo PostgreSQL LOCAL. Datos ficticios de volumen y permisos revertidos al terminar.
begin;
create function pg_temp.report_reject(command text, expected text) returns void
language plpgsql security invoker as $$
begin execute command; raise exception 'TEST_UNEXPECTED_SUCCESS';
exception when others then
  if sqlerrm='TEST_UNEXPECTED_SUCCESS' or strpos(sqlerrm,expected)=0 then raise; end if;
end $$;
insert into auth.users(id) select ('cccccccc-0000-4000-8000-' || lpad(i::text,12,'0'))::uuid from generate_series(1,7) i;
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
select ('cccccccc-0000-4000-8000-' || lpad(i::text,12,'0'))::uuid,'Operador de reporte ' || i,
  case i when 1 then 'admin' when 2 then 'mesa_partes' when 4 then 'consulta' when 6 then 'consulta' when 7 then 'admin' else 'gestor' end,
  (select id from public.departments where code=case when i in (5,6) then 'GM' else 'MP' end),i<>7
from generate_series(1,7) i;
insert into public.applicants(id,document_type,document_number,full_name,email)
values ('dddddddd-0000-4000-8000-000000000001','DNI','01234567','Solicitante de prueba de reporte','solo-prueba@example.invalid');
insert into public.cases(id,reference,request_id,request_hash,applicant_id,department_id,title,description,channel,status,
  priority,due_on,created_by,created_at,assigned_to)
select ('eeeeeeee-0000-4000-8000-' || lpad(i::text,12,'0'))::uuid,'REP-' || lpad(i::text,5,'0'),gen_random_uuid(),'local',
  'dddddddd-0000-4000-8000-000000000001',(select id from public.departments where code=case when i=1501 then 'GM' else 'MP' end),
  'Revisión número ' || i,'Descripción ficticia exclusiva para pruebas locales.','presencial',
  case i when 1 then 'atendido' when 3 then 'observado' when 4 then 'en_revision' else 'recibido' end,
  case i when 2 then 'urgente' else 'normal' end,
  case when i<=4 then (statement_timestamp() at time zone 'America/Lima')::date + case i when 1 then -1 when 2 then 0 when 3 then 3 else 4 end else null end,
  'cccccccc-0000-4000-8000-000000000001',
  case i when 1 then '2026-09-17 04:59:59+00'::timestamptz when 2 then '2026-09-17 05:00:00+00'::timestamptz
    when 3 then '2026-09-18 04:59:59+00'::timestamptz else '2026-09-18 05:00:00+00'::timestamptz end,
  case when i=2 then 'cccccccc-0000-4000-8000-000000000003'::uuid else null end
from generate_series(1,1501) i;

set local role authenticated;
select set_config('request.jwt.claim.sub','cccccccc-0000-4000-8000-000000000001',true);
do $$ declare report jsonb; receipt jsonb; bad jsonb; begin
  if exists(select 1 from pg_proc where oid in ('public.export_case_report(jsonb)'::regprocedure,'public.case_receipt(uuid)'::regprocedure)
    and (prosecdef or provolatile<>'s')) then raise exception 'El reporte debe conservar RLS y una instantánea estable'; end if;
  if has_function_privilege('anon','public.export_case_report(jsonb)','EXECUTE')
     or has_function_privilege('anon','public.case_receipt(uuid)','EXECUTE') then raise exception 'Descargas habilitadas a anónimos'; end if;
  report:=public.export_case_report();
  if jsonb_array_length(report->'rows')<>1501 then raise exception 'Reporte truncado por paginación'; end if;
  if report::text like '%01234567%' or report::text like '%solo-prueba@%' or report::text like '%Solicitante de prueba%' then
    raise exception 'El reporte contiene identidad o contactos del solicitante'; end if;
  if (select count(distinct item->>'id') from jsonb_array_elements(report->'rows') item)<>1501 then
    raise exception 'Reporte duplicado'; end if;
  report:=public.export_case_report('{"received_from":"2026-09-17","received_to":"2026-09-17"}');
  if jsonb_array_length(report->'rows')<>2 then raise exception 'Límite de día en Chiclayo incorrecto'; end if;
  report:=public.export_case_report(jsonb_build_object('query','REP-00002','status','recibido','priority','urgente',
    'assignee','cccccccc-0000-4000-8000-000000000003','due','today','pending_only',true,
    'department_id',(select id from public.departments where code='MP'),
    'procedure_id',(select id from public.procedures where code='GENERAL')));
  if jsonb_array_length(report->'rows')<>1 or report->'rows'->0->>'reference'<>'REP-00002' then raise exception 'Filtros combinados incorrectos'; end if;
  if jsonb_array_length(public.export_case_report('{"due":"overdue"}')->'rows')<>0 then raise exception 'Atendido contado como vencido'; end if;
  if jsonb_array_length(public.export_case_report('{"due":"soon"}')->'rows')<>1 then raise exception 'Próximos tres días incorrectos'; end if;
  if jsonb_array_length(public.export_case_report('{"due":"none"}')->'rows')<>1497 then raise exception 'Filtro sin fecha incorrecto'; end if;
  if jsonb_array_length(public.export_case_report('{"assignee":"unassigned"}')->'rows')<>1500 then raise exception 'Filtro sin responsable incorrecto'; end if;
  if jsonb_array_length(public.export_case_report('{"query":"sin resultados"}')->'rows')<>0 then raise exception 'Consulta vacía incorrecta'; end if;
  receipt:=public.case_receipt('eeeeeeee-0000-4000-8000-000000000002');
  if receipt->'case'->'applicant'->>'document_masked'<>'****4567' or receipt::text like '%01234567%'
     or receipt::text like '%solo-prueba@%' then raise exception 'Identidad sin minimizar en constancia'; end if;
  if (receipt->'case'->>'created_at')::timestamptz<>'2026-09-17T05:00:00+00:00'::timestamptz or receipt->'case'->>'document_count'<>'0' then
    raise exception 'Contenido de constancia incorrecto'; end if;
  foreach bad in array array['[]'::jsonb,'{"status":"inventado"}','{"department_id":"otra"}',
    '{"pending_only":"false"}','{"received_to":"2026-02-30"}','{"received_from":"2026-10-02","received_to":"2026-10-01"}',
    '{"received_to":"9999-12-31"}','{"received_from":"tomorrow"}','{"desconocido":true}'] loop
    perform pg_temp.report_reject(format('select public.export_case_report(%L)',bad),'');
  end loop;
end $$;

-- Administrador y mesa de partes ven el conjunto; gestor y consulta solo su área.
do $$ declare i int; report jsonb; expected int; begin
  for i in 1..6 loop
    perform set_config('request.jwt.claim.sub','cccccccc-0000-4000-8000-' || lpad(i::text,12,'0'),true);
    report:=public.export_case_report();
    expected:=case when i<=2 then 1501 when i<=4 then 1500 else 1 end;
    if jsonb_array_length(report->'rows')<>expected then raise exception 'Reporte fuera de alcance: rol %',i; end if;
    if i in (5,6) then
      perform pg_temp.report_reject('select public.case_receipt(''eeeeeeee-0000-4000-8000-000000000002'')','no está disponible');
      report:=public.export_case_report(jsonb_build_object('department_id',(select id from public.departments where code='MP')));
      if jsonb_array_length(report->'rows')<>0 then raise exception 'Un filtro amplió los permisos'; end if;
    else
      perform public.case_receipt('eeeeeeee-0000-4000-8000-000000000002');
    end if;
  end loop;
  perform set_config('request.jwt.claim.sub','cccccccc-0000-4000-8000-000000000003',true);
  if jsonb_array_length(public.export_case_report('{"assignee":"mine"}')->'rows')<>1 then raise exception 'Filtro Mis pendientes sin identidad del servidor'; end if;
  perform set_config('request.jwt.claim.sub','cccccccc-0000-4000-8000-000000000007',true);
  perform pg_temp.report_reject('select public.export_case_report()','perfil municipal activo');
  perform pg_temp.report_reject('select public.case_receipt(''eeeeeeee-0000-4000-8000-000000000002'')','perfil municipal activo');
end $$;

-- Aumento de volumen como propietario de la BD LOCAL, sin desactivar políticas.
reset role;
insert into public.cases(reference,request_id,request_hash,applicant_id,department_id,title,description,channel,created_by)
select 'LIM-' || i,gen_random_uuid(),'local','dddddddd-0000-4000-8000-000000000001',
  (select id from public.departments where code='MP'),'Solicitud local de volumen','Descripción local para comprobar el límite explícito.',
  'presencial','cccccccc-0000-4000-8000-000000000001'
from generate_series(1,8500) i;
set local role authenticated;
select set_config('request.jwt.claim.sub','cccccccc-0000-4000-8000-000000000001',true);
select pg_temp.report_reject('select public.export_case_report()','supera 10000');
do $$ declare report jsonb; begin
  report:=public.export_case_report(jsonb_build_object('department_id',(select id from public.departments where code='MP')));
  if jsonb_array_length(report->'rows')<>10000 then raise exception 'El límite exacto debe incluir todas las filas'; end if;
end $$;
reset role;
rollback;
