-- Administración del piloto: cambios autorizados, versiones e historial.
begin;

alter table public.departments add column version integer not null default 1 check (version > 0);
alter table public.procedures add column version integer not null default 1 check (version > 0);
alter table public.staff_profiles add column version integer not null default 1 check (version > 0);

create table public.admin_events (
  id bigint generated always as identity primary key,
  entity text not null check (entity in ('departments','procedures','staff_profiles')),
  record_id uuid not null,
  actor_id uuid not null references public.staff_profiles(user_id),
  actor_name text not null,
  reason text not null check (length(trim(reason)) between 10 and 500),
  before_data jsonb,
  after_data jsonb not null,
  created_at timestamptz not null default now()
);
create index admin_events_record_idx on public.admin_events(entity,record_id,id desc);
create index admin_events_actor_idx on public.admin_events(actor_id);
alter table public.admin_events enable row level security;
create policy admin_events_read on public.admin_events for select to authenticated
  using ((select private.staff_role()) = 'admin');
revoke all on public.admin_events from public,anon,authenticated;
revoke all on sequence public.admin_events_id_seq from public,anon,authenticated;
grant select on public.admin_events to authenticated;

-- El bloqueo compartido coordina las altas/derivaciones con la desactivación de áreas.
-- No se borran referencias históricas. Cuentas y fichas inactivas pueden conservar el área.
create function private.require_active_department() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_table_name in ('staff_profiles','procedures') then
    if not new.is_active then return new; end if;
  elsif tg_op = 'UPDATE' then
    if new.department_id is not distinct from old.department_id then return new; end if;
  end if;
  if new.department_id is not null then
    perform 1 from public.departments where id = new.department_id and is_active for share;
    if not found then raise exception 'Selecciona un área activa.'; end if;
  end if;
  return new;
end $$;
create trigger cases_active_department before insert or update of department_id on public.cases
  for each row execute function private.require_active_department();
create trigger staff_active_department before insert or update of department_id,is_active on public.staff_profiles
  for each row execute function private.require_active_department();
create trigger procedures_active_department before insert or update of department_id,is_active on public.procedures
  for each row execute function private.require_active_department();

create function private.admin_list_records(entity text, search_text text, start_index integer)
returns jsonb language plpgsql stable security definer set search_path = '' as $$
declare result jsonb;
begin
  if auth.uid() is null or private.staff_role() is distinct from 'admin' then
    raise exception 'Solo un administrador activo puede abrir Administración.'; end if;
  if search_text is null or length(search_text) > 100 or start_index is null or start_index < 0 then
    raise exception 'Búsqueda o página inválida.'; end if;
  if entity = 'departments' then
    select coalesce(jsonb_agg(to_jsonb(r) order by r.name,r.id),'[]') into result from (
      select * from public.departments
      where strpos(lower(name || ' ' || code),lower(trim(search_text))) > 0
      order by name,id limit 51 offset start_index
    ) r;
  elsif entity = 'procedures' then
    select coalesce(jsonb_agg(to_jsonb(r) order by r.name,r.id),'[]') into result from (
      select * from public.procedures
      where strpos(lower(name || ' ' || code),lower(trim(search_text))) > 0
      order by name,id limit 51 offset start_index
    ) r;
  elsif entity = 'staff_profiles' then
    select coalesce(jsonb_agg(to_jsonb(r) order by r.display_name,r.user_id),'[]') into result from (
      select * from public.staff_profiles
      where strpos(lower(display_name),lower(trim(search_text))) > 0
      order by display_name,user_id limit 51 offset start_index
    ) r;
  else raise exception 'Sección de Administración inválida.';
  end if;
  return result;
end $$;

create function private.admin_save_record(entity text, payload jsonb, expected_version integer, reason text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  actor public.staff_profiles;
  previous jsonb;
  result jsonb;
  target_id uuid;
  target_department uuid;
  active boolean;
  code_value text;
  name_value text;
  source_value text;
  role_value text;
  fee_value numeric;
  deadline_value integer;
  official boolean;
begin
  -- Serializa cambios administrativos. La autorización se vuelve a leer tras el bloqueo.
  perform pg_catalog.pg_advisory_xact_lock(716249103);
  select * into actor from public.staff_profiles where user_id = auth.uid() and is_active;
  if auth.uid() is null or actor.role is distinct from 'admin' then
    raise exception 'Solo un administrador activo puede guardar estos cambios.'; end if;
  if entity is null or entity not in ('departments','procedures','staff_profiles') then
    raise exception 'Sección de Administración inválida.'; end if;
  if payload is null or jsonb_typeof(payload) is distinct from 'object'
     or expected_version is null or expected_version < 0 then
    raise exception 'El registro o su versión no son válidos.'; end if;
  if coalesce(length(trim(reason)),0) not between 10 and 500 then
    raise exception 'Registra un motivo de 10 a 500 caracteres.'; end if;
  if jsonb_typeof(payload->'is_active') is distinct from 'boolean' then
    raise exception 'Indica si el registro está activo.'; end if;
  active := (payload->>'is_active')::boolean;
  target_id := (payload->>(case when entity='staff_profiles' then 'user_id' else 'id' end))::uuid;
  if target_id is null then raise exception 'Falta el identificador del registro.'; end if;
  target_department := nullif(payload->>'department_id','')::uuid;

  if entity = 'departments' then
    select to_jsonb(d) into previous from public.departments d where id = target_id for update;
  elsif entity = 'procedures' then
    select to_jsonb(p) into previous from public.procedures p where id = target_id for update;
  else
    select to_jsonb(s) into previous from public.staff_profiles s where user_id = target_id for update;
    if previous is null then raise exception 'La cuenta debe darse de alta antes de editar su perfil.'; end if;
  end if;
  if (previous is null and expected_version <> 0)
     or (previous is not null and (previous->>'version')::integer <> expected_version) then
    raise exception 'Otro usuario modificó el registro. Vuelve a la lista y abre la versión actual.'; end if;

  if entity in ('departments','procedures') then
    code_value := upper(trim(payload->>'code'));
    name_value := trim(payload->>'name');
    if code_value is null or code_value !~ '^[A-Z0-9][A-Z0-9_-]{1,19}$' then
      raise exception 'Código: usa de 2 a 20 letras, números, guion o guion bajo.'; end if;
    if coalesce(length(name_value),0) not between 3 and 120 then
      raise exception 'El nombre debe tener entre 3 y 120 caracteres.'; end if;
  end if;

  if entity = 'departments' then
    if payload->>'unit_type' is null or payload->>'unit_type' not in ('gerencia','punto_recepcion','referencia') then
      raise exception 'Selecciona un tipo de área válido.'; end if;
    source_value := nullif(trim(payload->>'source_url'),'');
    if source_value is not null and (length(source_value)>1000 or source_value !~ '^https://[^[:space:]/?#]+([/?#][^[:space:]]*)?$') then
      raise exception 'El enlace de referencia debe ser una dirección HTTPS válida.'; end if;
    if not active then
      if exists(select 1 from public.staff_profiles where department_id=target_id and is_active) then
        raise exception 'Reasigna o desactiva primero al personal activo de esta área.'; end if;
      if exists(select 1 from public.procedures where department_id=target_id and is_active) then
        raise exception 'Reasigna o desactiva primero los trámites activos de esta área.'; end if;
      if exists(select 1 from public.cases where department_id=target_id and status<>'archivado') then
        raise exception 'Esta área conserva expedientes sin archivar. Derívalos o concluye su archivo.'; end if;
    end if;
    if previous is null then
      insert into public.departments(id,code,name,is_active,unit_type,source_url)
        values(target_id,code_value,name_value,active,payload->>'unit_type',source_value)
        returning to_jsonb(departments.*) into result;
    else
      update public.departments set code=code_value,name=name_value,is_active=active,
        unit_type=payload->>'unit_type',source_url=source_value,version=version+1 where id=target_id
        returning to_jsonb(departments.*) into result;
    end if;
  elsif entity = 'procedures' then
    if jsonb_typeof(payload->'is_official') is distinct from 'boolean' then
      raise exception 'Indica si la ficha tiene sustento oficial.'; end if;
    official := (payload->>'is_official')::boolean;
    if length(coalesce(payload->>'requirements',''))>5000 or length(coalesce(payload->>'legal_basis',''))>2000 then
      raise exception 'Requisitos: máximo 5000 caracteres. Sustento: máximo 2000.'; end if;
    if official and coalesce(length(trim(payload->>'legal_basis')),0)=0 then
      raise exception 'Añade el sustento y la referencia antes de marcar la ficha oficial.'; end if;
    fee_value := nullif(payload->>'fee_pen','')::numeric;
    if fee_value is not null and (fee_value < 0 or fee_value > 9999999999.99 or fee_value <> round(fee_value,2)) then
      raise exception 'El importe debe ser no negativo y tener como máximo dos decimales.'; end if;
    if nullif(payload->>'deadline_days','') is not null then
      if (payload->>'deadline_days') !~ '^[0-9]+$' then raise exception 'El plazo debe ser un número entero.'; end if;
      deadline_value := (payload->>'deadline_days')::integer;
      if deadline_value not between 1 and 3650 then raise exception 'Plazo: indica entre 1 y 3650 días.'; end if;
    end if;
    if previous is null then
      insert into public.procedures(id,code,name,requirements,department_id,is_official,legal_basis,fee_pen,deadline_days,is_active)
        values(target_id,code_value,name_value,trim(coalesce(payload->>'requirements','')),target_department,official,
          nullif(trim(payload->>'legal_basis'),''),fee_value,deadline_value,active)
        returning to_jsonb(procedures.*) into result;
    else
      update public.procedures set code=code_value,name=name_value,
        requirements=trim(coalesce(payload->>'requirements','')),department_id=target_department,is_official=official,
        legal_basis=nullif(trim(payload->>'legal_basis'),''),fee_pen=fee_value,deadline_days=deadline_value,
        is_active=active,version=version+1 where id=target_id returning to_jsonb(procedures.*) into result;
    end if;
  else
    name_value := trim(payload->>'display_name');
    role_value := payload->>'role';
    if coalesce(length(name_value),0) not between 3 and 120 then raise exception 'El nombre debe tener entre 3 y 120 caracteres.'; end if;
    if role_value is null or role_value not in ('admin','mesa_partes','gestor','consulta') then
      raise exception 'Selecciona un rol válido.'; end if;
    if role_value in ('gestor','consulta') and target_department is null then
      raise exception 'Los perfiles Gestor y Consulta necesitan un área.'; end if;
    if target_id=auth.uid() and (not active or role_value<>'admin') then
      raise exception 'No puedes desactivar tu propia cuenta ni retirar tu rol de administrador.'; end if;
    update public.staff_profiles set display_name=name_value,role=role_value,department_id=target_department,
      is_active=active,version=version+1 where user_id=target_id returning to_jsonb(staff_profiles.*) into result;
  end if;

  insert into public.admin_events(entity,record_id,actor_id,actor_name,reason,before_data,after_data)
    values(entity,target_id,actor.user_id,actor.display_name,trim(reason),previous,result);
  return result;
exception
  when unique_violation then raise exception 'Ese código ya existe. Usa otro o edita el registro existente.';
  when invalid_text_representation or numeric_value_out_of_range then
    raise exception 'Revisa los identificadores y los valores numéricos del formulario.';
end $$;

create function public.admin_list_records(entity text, search_text text default '', start_index integer default 0)
returns jsonb language sql stable security invoker set search_path = '' as $$
  select private.admin_list_records(entity,search_text,start_index)
$$;
create function public.admin_save_record(entity text, payload jsonb, expected_version integer, reason text)
returns jsonb language sql security invoker set search_path = '' as $$
  select private.admin_save_record(entity,payload,expected_version,reason)
$$;
revoke execute on function private.require_active_department() from public,anon,authenticated;
revoke execute on function private.admin_list_records(text,text,integer),
  private.admin_save_record(text,jsonb,integer,text),public.admin_list_records(text,text,integer),
  public.admin_save_record(text,jsonb,integer,text) from public,anon,authenticated;
grant execute on function private.admin_list_records(text,text,integer),
  private.admin_save_record(text,jsonb,integer,text),public.admin_list_records(text,text,integer),
  public.admin_save_record(text,jsonb,integer,text) to authenticated;
commit;
