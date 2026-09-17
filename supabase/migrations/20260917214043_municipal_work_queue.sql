-- Trámite, responsable y organización del trabajo. Conserva la RLS por área.
begin;
alter table public.cases
  add column procedure_id uuid references public.procedures(id) on delete restrict,
  add column procedure_snapshot jsonb,
  add column assigned_to uuid references public.staff_profiles(user_id) on delete restrict,
  add constraint cases_procedure_snapshot_check check (
    (procedure_id is null and procedure_snapshot is null) or
    (procedure_id is not null and procedure_snapshot is not null and jsonb_typeof(procedure_snapshot)='object')
  );
create index cases_procedure_idx on public.cases(procedure_id);
create index cases_assigned_created_idx on public.cases(assigned_to,created_at desc,id desc);
alter table public.case_events add column work_before jsonb, add column work_after jsonb;
comment on column public.cases.procedure_snapshot is 'Ficha vigente al clasificar el expediente. No se recalculan tarifas ni plazos.';
comment on column public.cases.assigned_to is 'Responsable operativo del área. No amplía permisos de lectura ni sustituye la RLS.';

create function private.case_work_snapshot(target public.cases) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select jsonb_build_object('procedure_id',target.procedure_id,'procedure_snapshot',target.procedure_snapshot,
    'assigned_to',target.assigned_to,'assignee_name',(select display_name from public.staff_profiles where user_id=target.assigned_to),
    'priority',target.priority,'due_on',target.due_on)
$$;

create function private.prepare_case_work() returns trigger
language plpgsql security definer set search_path = '' as $$
declare ficha public.procedures; worker public.staff_profiles; changed boolean;
begin
  if tg_op='INSERT' then
    if new.procedure_id is null then
      select id into new.procedure_id from public.procedures where code='GENERAL' and is_active;
    end if;
    changed := true;
  else
    changed := new.procedure_id is distinct from old.procedure_id;
    if new.department_id is distinct from old.department_id then new.assigned_to := null; end if;
  end if;
  if changed then
    select * into ficha from public.procedures where id=new.procedure_id and is_active for share;
    if not found then raise exception 'Selecciona un trámite activo del catálogo.'; end if;
    new.procedure_snapshot := to_jsonb(ficha);
  end if;
  if tg_op='INSERT' then changed := new.assigned_to is not null;
  else changed := new.assigned_to is distinct from old.assigned_to; end if;
  if changed and new.assigned_to is not null then
    select * into worker from public.staff_profiles where user_id=new.assigned_to for share;
    if not found or not worker.is_active or worker.role not in ('admin','mesa_partes','gestor')
       or worker.department_id is distinct from new.department_id then
      raise exception 'El responsable debe ser una persona activa con permiso de atención en esta área.';
    end if;
  end if;
  return new;
end $$;
create trigger cases_prepare_work before insert or update of procedure_id,assigned_to,department_id on public.cases
  for each row execute function private.prepare_case_work();

-- Evita dejar trabajo pendiente a una cuenta que ya no podrá atenderlo.
create function private.protect_assigned_work() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if (not new.is_active or new.role='consulta' or new.department_id is distinct from old.department_id)
     and exists(select 1 from public.cases where assigned_to=new.user_id and status not in ('atendido','archivado')) then
    raise exception 'Reasigna o libera primero los expedientes pendientes de esta persona.';
  end if;
  return new;
end $$;
create trigger staff_protect_assigned_work before update of role,is_active,department_id on public.staff_profiles
  for each row execute function private.protect_assigned_work();

create function private.set_case_work(case_id uuid, expected_version integer, procedure_id uuid,
  assigned_to uuid, priority text, due_on date, note text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare actor public.staff_profiles; target public.cases; previous jsonb; next_work jsonb;
begin
  select * into actor from public.staff_profiles where user_id=auth.uid() and is_active for share;
  if auth.uid() is null or actor.role is null or actor.role not in ('admin','mesa_partes','gestor') then
    raise exception 'Tu perfil no puede organizar expedientes.'; end if;
  select * into target from public.cases c where c.id=case_id for update;
  if not found or (actor.role='gestor' and actor.department_id is distinct from target.department_id) then
    raise exception 'El expediente no está disponible para tu área.'; end if;
  if target.status in ('atendido','archivado') then raise exception 'El expediente ya está cerrado para organización.'; end if;
  if expected_version is null or target.version<>expected_version then
    raise exception 'Otro usuario modificó el expediente. Actualiza antes de continuar.'; end if;
  if procedure_id is null then raise exception 'Selecciona un trámite del catálogo.'; end if;
  if priority is null or priority not in ('normal','alta','urgente') then raise exception 'Selecciona una prioridad válida.'; end if;
  if coalesce(length(trim(note)),0) not between 10 and 2000 then raise exception 'Registra un motivo de 10 a 2000 caracteres.'; end if;
  if target.procedure_id is not distinct from procedure_id and target.assigned_to is not distinct from assigned_to
     and target.priority=priority and target.due_on is not distinct from due_on then
    raise exception 'Modifica el trámite, responsable, prioridad o fecha objetivo antes de guardar.'; end if;
  previous := private.case_work_snapshot(target);
  update public.cases c set procedure_id=set_case_work.procedure_id,assigned_to=set_case_work.assigned_to,
    priority=set_case_work.priority,due_on=set_case_work.due_on,version=c.version+1,updated_at=now()
    where c.id=case_id returning * into target;
  next_work := private.case_work_snapshot(target);
  insert into public.case_events(case_id,action,actor_id,actor_name,from_status,to_status,
    from_department_id,to_department_id,note,work_before,work_after)
    values(target.id,'organización',auth.uid(),actor.display_name,target.status,target.status,
      target.department_id,target.department_id,trim(note),previous,next_work);
  return to_jsonb(target)-'request_hash';
end $$;
create function public.set_case_work(case_id uuid, expected_version integer, procedure_id uuid,
  assigned_to uuid, priority text, due_on date, note text) returns jsonb
language sql security invoker set search_path = '' as $$
  select private.set_case_work(case_id,expected_version,procedure_id,assigned_to,priority,due_on,note)
$$;
revoke execute on function private.case_work_snapshot(public.cases),private.prepare_case_work(),
  private.protect_assigned_work() from public,anon,authenticated;
revoke execute on function private.set_case_work(uuid,integer,uuid,uuid,text,date,text),
  public.set_case_work(uuid,integer,uuid,uuid,text,date,text) from public,anon,authenticated;
grant execute on function private.set_case_work(uuid,integer,uuid,uuid,text,date,text),
  public.set_case_work(uuid,integer,uuid,uuid,text,date,text) to authenticated;

-- Las sustituciones de registro y derivación se incluyen a continuación.

create or replace function private.register_case(payload jsonb) returns jsonb
language plpgsql security definer set search_path = ''
as $$
  declare actor public.staff_profiles; target public.cases; applicant uuid; dept uuid;
    request uuid; fingerprint text; year_number integer; sequence_number bigint;
    doc_type text; doc_number text; person_name text;
  begin
    select * into actor from public.staff_profiles where user_id=auth.uid() and is_active for share;
    if auth.uid() is null or actor.role is null or actor.role not in ('admin','mesa_partes') then
      raise exception 'Solo Mesa de Partes o un administrador puede registrar expedientes.'; end if;
    request := (payload->>'request_id')::uuid;
    if request is null then raise exception 'Falta el identificador del intento de registro.'; end if;
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(auth.uid()::text || request::text,0));
    fingerprint := md5(payload::text);
    select * into target from public.cases where created_by=auth.uid() and request_id=request;
    if found then
      if target.request_hash <> fingerprint then raise exception 'Este intento ya fue usado con otros datos. Abre un nuevo formulario.'; end if;
      return to_jsonb(target) - 'request_hash';
    end if;
    dept := (payload->>'department_id')::uuid;
    if not exists(select 1 from public.departments where id=dept and is_active) then raise exception 'El área de destino no está activa.'; end if;
    if coalesce(length(trim(payload->>'title')),0) not between 5 and 160
       or coalesce(length(trim(payload->>'description')),0) not between 10 and 5000 then
      raise exception 'Revisa la longitud del asunto y la descripción.'; end if;
    if coalesce(payload->>'channel','') not in ('presencial','virtual','correo')
       or coalesce(payload->>'priority','') not in ('normal','alta','urgente') then
      raise exception 'Canal o prioridad inválidos.'; end if;
    doc_type := payload->>'document_type'; doc_number := upper(trim(payload->>'document_number'));
    person_name := trim(payload->>'applicant_name');
    if coalesce(length(person_name),0) not between 3 and 180 then raise exception 'Revisa el nombre del solicitante.'; end if;
    if nullif(trim(payload->>'email'),'') is not null and
       (length(payload->>'email') > 254 or (payload->>'email') !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$') then
      raise exception 'El correo de contacto no es válido.'; end if;
    insert into public.applicants(document_type,document_number,full_name,email,phone)
      values (doc_type,doc_number,person_name,nullif(trim(payload->>'email'),''),nullif(trim(payload->>'phone'),''))
      on conflict(document_type,document_number) do nothing;
    select id into applicant from public.applicants where document_type=doc_type and document_number=doc_number;
    if not exists(select 1 from public.applicants where id=applicant and lower(full_name)=lower(person_name)) then
      raise exception 'Ese documento ya está registrado con otro nombre. Solicita la verificación del administrador.'; end if;
    year_number := extract(year from now() at time zone 'America/Lima');
    insert into private.case_counters(year,last_value) values(year_number,1)
      on conflict(year) do update set last_value=private.case_counters.last_value+1 returning last_value into sequence_number;
    insert into public.cases(reference,request_id,request_hash,applicant_id,department_id,title,description,channel,priority,due_on,created_by,procedure_id,assigned_to)
      values('EXP-' || year_number || '-' || lpad(sequence_number::text,greatest(6,length(sequence_number::text)),'0'),
        request,fingerprint,applicant,dept,trim(payload->>'title'),trim(payload->>'description'),
        payload->>'channel',payload->>'priority',nullif(payload->>'due_on','')::date,auth.uid(),nullif(payload->>'procedure_id','')::uuid,nullif(payload->>'assigned_to','')::uuid) returning * into target;
    insert into public.case_events(case_id,action,actor_id,actor_name,to_status,to_department_id,note,work_after)
      values(target.id,'registro',auth.uid(),actor.display_name,'recibido',dept,'Solicitud recibida y registrada en mesa de partes.',private.case_work_snapshot(target));
    return to_jsonb(target) - 'request_hash';
  end
$$;

create or replace function private.advance_case(case_id uuid, expected_version integer, new_status text, new_department uuid, note text) returns jsonb
language plpgsql security definer set search_path = ''
as $$
  declare actor public.staff_profiles; target public.cases; old_status text; old_department uuid; allowed boolean; previous_work jsonb;
  begin
    select * into actor from public.staff_profiles where user_id=auth.uid() and is_active for share;
    if auth.uid() is null or actor.role is null or actor.role not in ('admin','mesa_partes','gestor') then
      raise exception 'Tu perfil no puede actualizar expedientes.'; end if;
    select * into target from public.cases c where c.id=case_id for update;
    if not found or (actor.role='gestor' and actor.department_id is distinct from target.department_id) then
      raise exception 'El expediente no está disponible para tu área.'; end if;
    if expected_version is null or target.version <> expected_version then
      raise exception 'Otro usuario modificó el expediente. Actualiza antes de continuar.'; end if;
    if coalesce(length(trim(note)),0) not between 10 and 2000 then raise exception 'Registra un motivo de 10 a 2000 caracteres.'; end if;
    if not exists(select 1 from public.departments where id=new_department and is_active) then raise exception 'Selecciona un área activa.'; end if;
    allowed := case target.status
      when 'recibido' then new_status in ('en_revision','observado')
      when 'en_revision' then new_status in ('observado','atendido')
      when 'observado' then new_status='en_revision'
      when 'atendido' then new_status='archivado'
      else false end;
    if new_status=target.status and new_department<>target.department_id and target.status not in ('atendido','archivado') then allowed:=true; end if;
    if allowed is distinct from true then raise exception 'Cambio de estado no permitido.'; end if;
    previous_work:=private.case_work_snapshot(target);
    old_status:=target.status; old_department:=target.department_id;
    update public.cases c set status=new_status,department_id=new_department,version=c.version+1,updated_at=now()
      where c.id=case_id returning * into target;
    insert into public.case_events(case_id,action,actor_id,actor_name,from_status,to_status,from_department_id,to_department_id,note,work_before,work_after)
      values(target.id,case when old_department<>new_department then 'derivación' else 'cambio de estado' end,
             auth.uid(),actor.display_name,old_status,new_status,old_department,new_department,trim(note),previous_work,private.case_work_snapshot(target));
    return to_jsonb(target) - 'request_hash';
  end
$$;

commit;
