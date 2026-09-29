-- Fuente y vigencia del catálogo, sin inventar importes ni plazos oficiales.
begin;
alter table public.procedures add column source_url text,
  add column valid_from date,add column valid_until date;
alter table public.procedures add constraint procedures_source_url_check
  check(source_url is null or (length(source_url)<=1000 and source_url ~ '^https://[^[:space:]/?#]+([/?#][^[:space:]]*)?$'));
alter table public.procedures add constraint procedures_validity_check
  check(valid_from is null or valid_until is null or valid_until>=valid_from);
alter table public.procedures add constraint procedures_official_source_check
  check(not is_official or source_url is not null);
update public.procedures set source_url='https://www.munichiclayo.gob.pe/mpv/',version=version+1
where code='GENERAL' and not is_official and source_url is null;
-- Ubigeo del distrito sede, no de toda la provincia. Fuente SUNAT, anexo 2:
-- https://www.sunat.gob.pe/legislacion/superin/2001/100.htm
update public.municipal_settings set ubigeo='140101'
where id=1 and ubigeo is null and institution_name='Municipalidad Provincial de Chiclayo';
comment on column public.municipal_settings.ubigeo is 'Ubigeo de seis dígitos del distrito sede: Chiclayo, provincia Chiclayo, departamento Lambayeque.';
create or replace function private.admin_save_record(entity text, payload jsonb, expected_version integer, reason text)
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
  official boolean; start_value date; end_value date;
begin
  if entity='applicants' then return private.save_applicant(payload,expected_version,reason); end if;
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
    source_value:=case when payload ? 'source_url' then nullif(trim(payload->>'source_url'),'') else previous->>'source_url' end;
    start_value:=case when payload ? 'valid_from' then nullif(payload->>'valid_from','')::date else (previous->>'valid_from')::date end;
    end_value:=case when payload ? 'valid_until' then nullif(payload->>'valid_until','')::date else (previous->>'valid_until')::date end;
    if source_value is not null and (length(source_value)>1000 or source_value !~ '^https://[^[:space:]/?#]+([/?#][^[:space:]]*)?$') then
      raise exception 'La fuente del trámite debe ser una dirección HTTPS válida.'; end if;
    if official and source_value is null then raise exception 'Añade una fuente verificable para el sustento oficial.'; end if;
    if start_value>end_value then raise exception 'El fin de vigencia no puede ser anterior al inicio.'; end if;
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
      insert into public.procedures(id,code,name,requirements,department_id,is_official,legal_basis,fee_pen,deadline_days,is_active,source_url,valid_from,valid_until)
        values(target_id,code_value,name_value,trim(coalesce(payload->>'requirements','')),target_department,official,
          nullif(trim(payload->>'legal_basis'),''),fee_value,deadline_value,active,source_value,start_value,end_value)
        returning to_jsonb(procedures.*) into result;
    else
      update public.procedures set code=code_value,name=name_value,
        requirements=trim(coalesce(payload->>'requirements','')),department_id=target_department,is_official=official,
        legal_basis=nullif(trim(payload->>'legal_basis'),''),fee_pen=fee_value,deadline_days=deadline_value,
        is_active=active,source_url=source_value,valid_from=start_value,valid_until=end_value,
        version=version+1 where id=target_id returning to_jsonb(procedures.*) into result;
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
  when invalid_datetime_format or datetime_field_overflow then raise exception 'Usa fechas válidas para la vigencia.';
  when unique_violation then raise exception 'Ese código ya existe. Usa otro o edita el registro existente.';
  when invalid_text_representation or numeric_value_out_of_range then
    raise exception 'Revisa los identificadores y los valores numéricos del formulario.';
end $$;
create or replace function private.prepare_case_work() returns trigger
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
    select * into ficha from public.procedures where id=new.procedure_id and is_active
      and (valid_from is null or valid_from <= (now() at time zone 'America/Lima')::date)
      and (valid_until is null or valid_until >= (now() at time zone 'America/Lima')::date) for share;
    if not found then raise exception 'Selecciona un trámite activo y vigente del catálogo.'; end if;
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
commit;
