begin;

-- Un valor JSON, una instantánea MVCC: no depende del límite REST de 1000 filas
-- ni mezcla páginas obtenidas antes y después de una derivación. Ambas funciones
-- son INVOKER y conservan las políticas RLS del operador que solicita el archivo.
create function public.export_case_report(report_filters jsonb default '{}'::jsonb)
returns jsonb language plpgsql stable security invoker set search_path = ''
as $$
declare
  f jsonb := coalesce(report_filters, '{}'::jsonb);
  part record;
  actor public.staff_profiles;
  at_time timestamptz := statement_timestamp();
  local_day date := (statement_timestamp() at time zone 'America/Lima')::date;
  term text;
  wanted_status text;
  dept uuid;
  proc uuid;
  owner_filter text;
  worker uuid;
  wanted_priority text;
  due_filter text;
  pending boolean;
  from_day date;
  to_day date;
  rows_json jsonb;
  normalized jsonb;
begin
  select * into actor from public.staff_profiles where user_id=auth.uid() and is_active;
  if actor.user_id is null then raise exception 'Inicia sesión con un perfil municipal activo.'; end if;
  if jsonb_typeof(f)<>'object' then raise exception 'Los filtros del reporte no son válidos.'; end if;
  for part in select key,value from jsonb_each(f) loop
    if part.key not in ('query','status','department_id','procedure_id','assignee','priority','due',
                        'pending_only','received_from','received_to') then
      raise exception 'El reporte contiene un filtro desconocido.';
    end if;
    if part.key='pending_only' then
      if jsonb_typeof(part.value) not in ('boolean','null') then raise exception 'Indica si deseas ver solamente pendientes.'; end if;
    elsif jsonb_typeof(part.value) not in ('string','null') then
      raise exception 'Revisa los valores de los filtros del reporte.';
    end if;
  end loop;
  term := left(btrim(regexp_replace(coalesce(f->>'query',''),'[^0-9A-Za-zÀ-ÿ -]',' ','g')),60);
  wanted_status := coalesce(f->>'status','');
  dept := nullif(f->>'department_id','')::uuid;
  proc := nullif(f->>'procedure_id','')::uuid;
  owner_filter := coalesce(f->>'assignee','');
  worker := case when owner_filter='mine' then auth.uid()
    when owner_filter in ('','unassigned') then null else owner_filter::uuid end;
  wanted_priority := coalesce(f->>'priority','');
  due_filter := coalesce(f->>'due','');
  pending := coalesce((f->>'pending_only')::boolean,false);
  if wanted_status not in ('','recibido','en_revision','observado','atendido','archivado')
     or wanted_priority not in ('','normal','alta','urgente')
     or due_filter not in ('','overdue','today','soon','none') then
    raise exception 'Revisa los filtros de estado, prioridad y fecha objetivo.';
  end if;
  if (nullif(f->>'received_from','') is not null and f->>'received_from' !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
     or (nullif(f->>'received_to','') is not null and f->>'received_to' !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$') then
    raise exception 'Usa el formato AAAA-MM-DD para las fechas de ingreso.';
  end if;
  from_day := nullif(f->>'received_from','')::date;
  to_day := nullif(f->>'received_to','')::date;
  if from_day>to_day or to_day='9999-12-31'::date then
    raise exception 'Revisa el intervalo de fechas de ingreso.';
  end if;
  normalized := jsonb_build_object('query',term,'status',wanted_status,'department_id',dept,
    'procedure_id',proc,'assignee',owner_filter,'priority',wanted_priority,'due',due_filter,
    'pending_only',pending,'received_from',from_day,'received_to',to_day);

  with matches as materialized (
    select c.id,c.reference,c.title,c.status,c.priority,c.channel,c.created_at,c.due_on,c.version,
      c.department_id,d.name as department_name,c.procedure_id,
      c.procedure_snapshot->>'name' as procedure_name,c.assigned_to,s.display_name as assignee_name
    from public.cases c
    join public.departments d on d.id=c.department_id
    left join public.staff_profiles s on s.user_id=c.assigned_to
    where (term='' or strpos(lower(c.reference),lower(term))>0 or strpos(lower(c.title),lower(term))>0)
      and (wanted_status='' or c.status=wanted_status)
      and (dept is null or c.department_id=dept)
      and (proc is null or c.procedure_id=proc)
      and (wanted_priority='' or c.priority=wanted_priority)
      and (owner_filter='' or (owner_filter='unassigned' and c.assigned_to is null) or c.assigned_to=worker)
      and (not (pending or due_filter in ('overdue','today','soon')) or c.status not in ('atendido','archivado'))
      and (due_filter='' or (due_filter='none' and c.due_on is null)
        or (due_filter='overdue' and c.due_on<local_day)
        or (due_filter='today' and c.due_on=local_day)
        or (due_filter='soon' and c.due_on>local_day and c.due_on<=local_day+3))
      and (from_day is null or c.created_at >= (from_day::timestamp at time zone 'America/Lima'))
      and (to_day is null or c.created_at < ((to_day+1)::timestamp at time zone 'America/Lima'))
    order by c.created_at desc,c.id desc limit 10001
  )
  select coalesce(jsonb_agg(to_jsonb(m) order by m.created_at desc,m.id desc),'[]'::jsonb)
    into rows_json from matches m;
  if jsonb_array_length(rows_json)>10000 then
    raise exception 'La consulta supera 10000 expedientes. Reduce el período o aplica más filtros.';
  end if;
  return jsonb_build_object(
    'institution_name',(select institution_name from public.municipal_settings where id=1),
    'issued_at',at_time,'local_date',local_day,'issued_by',actor.display_name,
    'scope',case when actor.role in ('admin','mesa_partes') then 'Todos los expedientes'
      else coalesce((select name from public.departments where id=actor.department_id),'Sin área asignada') end,
    'filters',normalized,
    'filter_labels',jsonb_build_object(
      'department_id',(select name from public.departments where id=dept),
      'procedure_id',(select name from public.procedures where id=proc),
      'assignee',(select display_name from public.staff_profiles where user_id=worker)),
    'rows',rows_json);
exception when data_exception then
  raise exception 'Revisa las fechas y los identificadores de los filtros del reporte.';
end $$;

create function public.case_receipt(case_id uuid) returns jsonb
language plpgsql stable security invoker set search_path = ''
as $$
declare result jsonb;
begin
  if (select private.staff_role()) is null then
    raise exception 'Inicia sesión con un perfil municipal activo.';
  end if;
  select jsonb_build_object(
    'institution_name',(select institution_name from public.municipal_settings where id=1),
    'issued_at',statement_timestamp(),
    'case',jsonb_build_object(
      'id',c.id,'reference',c.reference,'title',c.title,'description',c.description,
      'channel',c.channel,'created_at',c.created_at,'status',c.status,'version',c.version,
      'department_name',d.name,'procedure_name',c.procedure_snapshot->>'name',
      'document_count',(select count(*) from public.case_documents cd where cd.case_id=c.id),
      'applicant',jsonb_build_object('full_name',a.full_name,'document_type',a.document_type,
        'document_masked',repeat('*',greatest(length(a.document_number)-4,0)) || right(a.document_number,4))))
    into result from public.cases c
    join public.applicants a on a.id=c.applicant_id
    join public.departments d on d.id=c.department_id
    where c.id=case_receipt.case_id;
  if result is null then
    raise exception 'El expediente ya no está disponible en tu área. Actualiza la bandeja.';
  end if;
  return result;
end $$;

revoke execute on function public.export_case_report(jsonb),public.case_receipt(uuid) from public,anon;
grant execute on function public.export_case_report(jsonb),public.case_receipt(uuid) to authenticated;
comment on function public.export_case_report(jsonb) is 'Reporte completo con RLS en una instantánea. Rechaza más de 10000 resultados sin truncar.';
comment on function public.case_receipt(uuid) is 'Datos mínimos para una constancia del piloto, con identidad parcial y situación actual.';
commit;
