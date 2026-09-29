-- Correcciones autorizadas e instantánea del solicitante por expediente.
begin;
alter table public.applicants
  add column version integer not null default 1 check(version>0),
  add column updated_at timestamptz not null default now();
alter table public.cases add column applicant_snapshot jsonb;
update public.cases c set applicant_snapshot=jsonb_build_object(
  'full_name',a.full_name,'document_type',a.document_type,'document_number',a.document_number,
  'email',a.email,'phone',a.phone,'captured_at',statement_timestamp(),'origin','migration_current_record')
from public.applicants a where a.id=c.applicant_id;
alter table public.cases alter column applicant_snapshot set not null;
alter table public.cases add constraint cases_applicant_snapshot_check check(
  jsonb_typeof(applicant_snapshot)='object'
  and applicant_snapshot ?& array['full_name','document_type','document_number','email','phone','captured_at','origin']
  and jsonb_typeof(applicant_snapshot->'full_name')='string'
  and jsonb_typeof(applicant_snapshot->'document_number')='string');
comment on column public.cases.applicant_snapshot is
  'Datos declarados al registrar. Inmutable. Los anteriores a la migración indican migration_current_record; no se presume su contacto histórico.';
alter table public.admin_events drop constraint admin_events_entity_check;
alter table public.admin_events add constraint admin_events_entity_check check(
  entity in ('departments','procedures','staff_profiles','staff_invitations','applicants'));

create function private.protect_applicant_snapshot() returns trigger
language plpgsql security definer set search_path='' as $$
begin
  if tg_op='UPDATE' then
    if new.applicant_snapshot is distinct from old.applicant_snapshot or new.applicant_id<>old.applicant_id then
      raise exception 'Los datos de recepción se conservan en el historial del expediente.';
    end if;
  elsif new.applicant_snapshot is null then
    select jsonb_build_object('full_name',a.full_name,'document_type',a.document_type,
      'document_number',a.document_number,'email',a.email,'phone',a.phone,
      'captured_at',statement_timestamp(),'origin','current_record')
      into new.applicant_snapshot from public.applicants a where a.id=new.applicant_id;
  end if;
  return new;
end $$;
create trigger cases_protect_applicant_snapshot before insert or update of applicant_id,applicant_snapshot
on public.cases for each row execute function private.protect_applicant_snapshot();
revoke all on function private.protect_applicant_snapshot() from public,anon,authenticated;

create function private.save_applicant(payload jsonb,expected_version integer,reason text)
returns jsonb language plpgsql security definer set search_path='' as $$
declare actor public.staff_profiles; previous public.applicants; result public.applicants;
  kind text; number_value text; name_value text; email_value text; phone_value text;
begin
  perform pg_catalog.pg_advisory_xact_lock(716249103);
  select * into actor from public.staff_profiles where user_id=auth.uid() and is_active;
  if auth.uid() is null or actor.role is distinct from 'admin' then
    raise exception 'Solo un administrador activo puede corregir solicitantes.'; end if;
  if jsonb_typeof(payload) is distinct from 'object' or coalesce(length(trim(reason)),0) not between 10 and 500 then
    raise exception 'Completa los datos y un motivo de 10 a 500 caracteres.'; end if;
  select * into previous from public.applicants where id=(payload->>'id')::uuid for update;
  if previous.id is null then raise exception 'Selecciona un solicitante registrado.'; end if;
  if expected_version is null or expected_version<>previous.version then
    raise exception 'Otro usuario corrigió este solicitante. Actualiza antes de continuar.'; end if;
  kind:=payload->>'document_type'; number_value:=upper(trim(payload->>'document_number'));
  name_value:=trim(payload->>'full_name'); email_value:=nullif(trim(payload->>'email'),'');
  phone_value:=nullif(trim(payload->>'phone'),'');
  if kind is null or number_value is null or not (
    (kind='DNI' and number_value ~ '^[0-9]{8}$') or (kind='RUC' and number_value ~ '^[0-9]{11}$')
    or (kind='CE' and number_value ~ '^[A-Z0-9]{9,12}$') or (kind='PAS' and number_value ~ '^[A-Z0-9]{6,15}$')) then
    raise exception 'Revisa el tipo y número de documento.'; end if;
  if coalesce(length(name_value),0) not between 3 and 180 then raise exception 'Revisa el nombre o razón social.'; end if;
  if email_value is not null and (length(email_value)>254 or email_value !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$') then
    raise exception 'Ingresa un correo válido o deja el campo vacío.'; end if;
  if phone_value is not null and phone_value !~ '^\+?[0-9 ()-]{7,20}$' then raise exception 'Revisa el teléfono de contacto.'; end if;
  if (previous.document_type,previous.document_number,previous.full_name,previous.email,previous.phone)
    is not distinct from (kind,number_value,name_value,email_value,phone_value) then
    raise exception 'Modifica algún dato antes de guardar la corrección.'; end if;
  update public.applicants set document_type=kind,document_number=number_value,full_name=name_value,
    email=email_value,phone=phone_value,version=version+1,updated_at=now()
    where id=previous.id returning * into result;
  insert into public.admin_events(entity,record_id,actor_id,actor_name,reason,before_data,after_data)
    values('applicants',result.id,actor.user_id,actor.display_name,trim(reason),to_jsonb(previous),to_jsonb(result));
  return to_jsonb(result);
exception when unique_violation then
  raise exception 'Ese documento ya pertenece a otra ficha. Revisa los registros antes de corregirlo.';
end $$;
revoke all on function private.save_applicant(jsonb,integer,text) from public,anon,authenticated;

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
    select id into applicant from public.applicants where document_type=doc_type and document_number=doc_number for share;
    if not exists(select 1 from public.applicants where id=applicant and lower(full_name)=lower(person_name)) then
      raise exception 'Ese documento ya está registrado con otro nombre. Solicita su corrección en Administración → Solicitantes.'; end if;
    year_number := extract(year from now() at time zone 'America/Lima');
    insert into private.case_counters(year,last_value) values(year_number,1)
      on conflict(year) do update set last_value=private.case_counters.last_value+1 returning last_value into sequence_number;
    insert into public.cases(reference,request_id,request_hash,applicant_id,department_id,title,description,channel,priority,due_on,created_by,procedure_id,assigned_to,applicant_snapshot)
      values('EXP-' || year_number || '-' || lpad(sequence_number::text,greatest(6,length(sequence_number::text)),'0'),
        request,fingerprint,applicant,dept,trim(payload->>'title'),trim(payload->>'description'),
        payload->>'channel',payload->>'priority',nullif(payload->>'due_on','')::date,auth.uid(),nullif(payload->>'procedure_id','')::uuid,nullif(payload->>'assigned_to','')::uuid,
        jsonb_build_object('full_name',person_name,'document_type',doc_type,'document_number',doc_number,
          'email',nullif(trim(payload->>'email'),''),'phone',nullif(trim(payload->>'phone'),''),
          'captured_at',statement_timestamp(),'origin','received')) returning * into target;
    insert into public.case_events(case_id,action,actor_id,actor_name,to_status,to_department_id,note,work_after)
      values(target.id,'registro',auth.uid(),actor.display_name,'recibido',dept,'Solicitud recibida y registrada en mesa de partes.',private.case_work_snapshot(target));
    return to_jsonb(target) - 'request_hash';
  end
$$;
create or replace function private.admin_list_records(entity text, search_text text, start_index integer)
returns jsonb language plpgsql stable security definer set search_path = '' as $$
declare result jsonb;
begin
  if auth.uid() is null or private.staff_role() is distinct from 'admin' then
    raise exception 'Solo un administrador activo puede abrir Administración.'; end if;
  if search_text is null or length(search_text) > 100 or start_index is null or start_index < 0 then
    raise exception 'Búsqueda o página inválida.'; end if;
  if entity = 'applicants' then
    select coalesce(jsonb_agg(to_jsonb(r) order by r.full_name,r.id),'[]') into result from (
      select * from public.applicants
      where strpos(lower(full_name || ' ' || document_number),lower(trim(search_text)))>0
      order by full_name,id limit 51 offset start_index
    ) r;
  elsif entity = 'departments' then
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
  official boolean;
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
create or replace function public.case_receipt(case_id uuid) returns jsonb
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
      'applicant',jsonb_build_object('full_name',c.applicant_snapshot->>'full_name','document_type',c.applicant_snapshot->>'document_type',
        'document_masked',repeat('*',greatest(length((c.applicant_snapshot->>'document_number'))-4,0)) || right((c.applicant_snapshot->>'document_number'),4))))
    into result from public.cases c
    join public.applicants a on a.id=c.applicant_id
    join public.departments d on d.id=c.department_id
    where c.id=case_receipt.case_id;
  if result is null then
    raise exception 'El expediente ya no está disponible en tu área. Actualiza la bandeja.';
  end if;
  return result;
end $$;
commit;
