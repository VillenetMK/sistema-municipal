-- MuniGest 0.1: expedientes internos. Proyecto municipal: lxvmwjcqdjoidgpinmgm.
-- Ninguna tarifa o plazo legal se inventa. El TUPA se incorpora después de validarlo.
begin;
create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated;

create table public.municipal_settings (
  id integer primary key check (id = 1),
  institution_name text not null default 'Municipalidad por configurar',
  ubigeo text check (ubigeo is null or ubigeo ~ '^[0-9]{6}$'),
  timezone text not null default 'America/Lima',
  configured boolean not null default false
);
insert into public.municipal_settings(id) values (1);

create table public.departments (
  id uuid primary key default gen_random_uuid(),
  code text not null unique check (length(code) between 2 and 20),
  name text not null check (length(name) between 3 and 120),
  is_active boolean not null default true
);
insert into public.departments(code,name) values
 ('MP','Mesa de Partes'),('GM','Gerencia Municipal'),('AC','Atención al Ciudadano');

create table public.staff_profiles (
  user_id uuid primary key references auth.users(id) on delete restrict,
  display_name text not null check (length(trim(display_name)) between 3 and 120),
  role text not null check (role in ('admin','mesa_partes','gestor','consulta')),
  department_id uuid references public.departments(id),
  is_active boolean not null default false,
  created_at timestamptz not null default now(),
  check (role in ('admin','mesa_partes') or department_id is not null)
);
create index staff_department_idx on public.staff_profiles(department_id);

create table public.procedures (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  requirements text not null default '',
  department_id uuid references public.departments(id),
  is_official boolean not null default false,
  legal_basis text,
  fee_pen numeric(12,2) check (fee_pen >= 0),
  deadline_days integer check (deadline_days > 0),
  is_active boolean not null default true,
  check (not is_official or nullif(trim(legal_basis),'') is not null)
);
create index procedures_department_idx on public.procedures(department_id);
insert into public.procedures(code,name,requirements)
values ('GENERAL','Solicitud general','Documento de solicitud y anexos que correspondan.');

create table public.applicants (
  id uuid primary key default gen_random_uuid(),
  document_type text not null check (document_type in ('DNI','RUC','CE','PAS')),
  document_number text not null,
  full_name text not null check (length(trim(full_name)) between 3 and 180),
  email text check (email is null or length(email) <= 254),
  phone text check (phone is null or phone ~ '^\+?[0-9 ()-]{7,20}$'),
  created_at timestamptz not null default now(),
  unique(document_type,document_number),
  check ((document_type='DNI' and document_number ~ '^[0-9]{8}$')
    or (document_type='RUC' and document_number ~ '^[0-9]{11}$')
    or (document_type='CE' and document_number ~ '^[A-Z0-9]{9,12}$')
    or (document_type='PAS' and document_number ~ '^[A-Z0-9]{6,15}$'))
);
create table private.case_counters (year integer primary key, last_value bigint not null);

create table public.cases (
  id uuid primary key default gen_random_uuid(),
  reference text not null unique,
  request_id uuid not null,
  request_hash text not null,
  applicant_id uuid not null references public.applicants(id),
  department_id uuid not null references public.departments(id),
  title text not null check (length(trim(title)) between 5 and 160),
  description text not null check (length(trim(description)) between 10 and 5000),
  channel text not null check (channel in ('presencial','virtual','correo')),
  priority text not null default 'normal' check (priority in ('normal','alta','urgente')),
  status text not null default 'recibido' check (status in ('recibido','en_revision','observado','atendido','archivado')),
  due_on date,
  created_by uuid not null references public.staff_profiles(user_id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  version integer not null default 1 check (version > 0),
  unique(created_by,request_id)
);
comment on column public.cases.due_on is 'Fecha objetivo INTERNA. No representa plazo legal ni suspensión de términos.';
create index cases_department_created_idx on public.cases(department_id,created_at desc,id desc);
create index cases_applicant_idx on public.cases(applicant_id);
create index cases_status_created_idx on public.cases(status,created_at desc,id desc);
create index cases_due_idx on public.cases(due_on) where status not in ('atendido','archivado');
create index cases_created_idx on public.cases(created_at desc,id desc);

create table public.case_events (
  id bigint generated always as identity primary key,
  case_id uuid not null references public.cases(id) on delete restrict,
  action text not null,
  actor_id uuid not null references public.staff_profiles(user_id),
  actor_name text not null,
  from_status text,
  to_status text not null,
  from_department_id uuid references public.departments(id),
  to_department_id uuid not null references public.departments(id),
  note text not null check (length(trim(note)) between 10 and 2000),
  created_at timestamptz not null default now()
);
create index events_case_created_idx on public.case_events(case_id,created_at desc,id desc);
create index events_actor_idx on public.case_events(actor_id);
create index events_from_department_idx on public.case_events(from_department_id);
create index events_to_department_idx on public.case_events(to_department_id);

create table public.case_documents (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete restrict,
  file_name text not null check (length(file_name) between 1 and 180 and file_name !~ '[/\\]'),
  object_path text not null unique,
  media_type text not null check (media_type in ('application/pdf','image/png','image/jpeg')),
  size_bytes bigint not null check (size_bytes between 1 and 10485760),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  created_by uuid not null default auth.uid() references public.staff_profiles(user_id),
  created_at timestamptz not null default now(),
  check (object_path ~ ('^' || case_id::text || '/[0-9a-f-]{36}\.(pdf|png|jpg|jpeg)$'))
);
create index documents_case_created_idx on public.case_documents(case_id,created_at desc);
create index documents_creator_idx on public.case_documents(created_by);

-- Funciones privilegiadas en esquema privado y con autorización comprobada en servidor.
create function private.staff_role() returns text
language sql stable security definer set search_path = ''
as $$ select role from public.staff_profiles where user_id = auth.uid() and is_active and auth.uid() is not null $$;

create function private.can_read_case(target uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select auth.uid() is not null and exists (
    select 1 from public.cases c join public.staff_profiles p on p.user_id = auth.uid()
    where c.id = target and p.is_active and
      (p.role in ('admin','mesa_partes') or p.department_id = c.department_id)
  )
$$;
create function private.can_write_case(target uuid) returns boolean
language sql stable security definer set search_path = ''
as $$
  select auth.uid() is not null and exists (
    select 1 from public.cases c join public.staff_profiles p on p.user_id = auth.uid()
    where c.id = target and p.is_active and c.status not in ('atendido','archivado') and
      (p.role in ('admin','mesa_partes') or (p.role='gestor' and p.department_id=c.department_id))
  )
$$;
create function private.document_access(path text, writing boolean) returns boolean
language plpgsql stable security invoker set search_path = ''
as $$
  declare target uuid;
  begin
    if path !~ '^[0-9a-f-]{36}/[0-9a-f-]{36}\.(pdf|png|jpg|jpeg)$' then return false; end if;
    begin target := split_part(path,'/',1)::uuid;
    exception when invalid_text_representation then return false; end;
    if writing then return private.can_write_case(target); end if;
    return private.can_read_case(target);
  end
$$;

-- Lecturas con RLS; el cliente no modifica roles, historial ni expedientes directamente.
alter table public.municipal_settings enable row level security;
alter table public.departments enable row level security;
alter table public.staff_profiles enable row level security;
alter table public.procedures enable row level security;
alter table public.applicants enable row level security;
alter table public.cases enable row level security;
alter table public.case_events enable row level security;
alter table public.case_documents enable row level security;
alter table private.case_counters enable row level security;

create policy settings_staff_read on public.municipal_settings for select to authenticated using ((select private.staff_role()) is not null);
create policy departments_staff_read on public.departments for select to authenticated using ((select private.staff_role()) is not null);
create policy profiles_staff_read on public.staff_profiles for select to authenticated using ((select private.staff_role()) is not null);
create policy procedures_staff_read on public.procedures for select to authenticated using ((select private.staff_role()) is not null);
create policy cases_staff_read on public.cases for select to authenticated using (private.can_read_case(id));
create policy applicants_staff_read on public.applicants for select to authenticated using (
 (select private.staff_role()) in ('admin','mesa_partes')
 or exists (select 1 from public.cases c where c.applicant_id = applicants.id)
);
create policy events_staff_read on public.case_events for select to authenticated using (private.can_read_case(case_id));
create policy documents_staff_read on public.case_documents for select to authenticated using (private.can_read_case(case_id));

-- Las operaciones de negocio se serializan y registran en una transacción.
create function private.register_case(payload jsonb) returns jsonb
language plpgsql security definer set search_path = ''
as $$
  declare actor public.staff_profiles; target public.cases; applicant uuid; dept uuid;
    request uuid; fingerprint text; year_number integer; sequence_number bigint;
    doc_type text; doc_number text; person_name text;
  begin
    select * into actor from public.staff_profiles where user_id=auth.uid() and is_active;
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
    insert into public.cases(reference,request_id,request_hash,applicant_id,department_id,title,description,channel,priority,due_on,created_by)
      values('EXP-' || year_number || '-' || lpad(sequence_number::text,greatest(6,length(sequence_number::text)),'0'),
        request,fingerprint,applicant,dept,trim(payload->>'title'),trim(payload->>'description'),
        payload->>'channel',payload->>'priority',nullif(payload->>'due_on','')::date,auth.uid()) returning * into target;
    insert into public.case_events(case_id,action,actor_id,actor_name,to_status,to_department_id,note)
      values(target.id,'registro',auth.uid(),actor.display_name,'recibido',dept,'Solicitud recibida y registrada en mesa de partes.');
    return to_jsonb(target) - 'request_hash';
  end
$$;
create function public.register_case(payload jsonb) returns jsonb
language sql security invoker set search_path = '' as $$ select private.register_case(payload) $$;

create function private.advance_case(case_id uuid, expected_version integer, new_status text, new_department uuid, note text) returns jsonb
language plpgsql security definer set search_path = ''
as $$
  declare actor public.staff_profiles; target public.cases; old_status text; old_department uuid; allowed boolean;
  begin
    select * into actor from public.staff_profiles where user_id=auth.uid() and is_active;
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
    old_status:=target.status; old_department:=target.department_id;
    update public.cases c set status=new_status,department_id=new_department,version=c.version+1,updated_at=now()
      where c.id=case_id returning * into target;
    insert into public.case_events(case_id,action,actor_id,actor_name,from_status,to_status,from_department_id,to_department_id,note)
      values(target.id,case when old_department<>new_department then 'derivación' else 'cambio de estado' end,
             auth.uid(),actor.display_name,old_status,new_status,old_department,new_department,trim(note));
    return to_jsonb(target) - 'request_hash';
  end
$$;
create function public.advance_case(case_id uuid, expected_version integer, new_status text, new_department uuid, note text) returns jsonb
language sql security invoker set search_path = ''
as $$ select private.advance_case(case_id,expected_version,new_status,new_department,note) $$;

create function public.case_metrics() returns jsonb language sql stable security invoker set search_path = ''
as $$ select jsonb_build_object(
 'total',count(*),
 'pending',count(*) filter(where status not in ('atendido','archivado')),
 'resolved',count(*) filter(where status in ('atendido','archivado')),
 'overdue',count(*) filter(where status not in ('atendido','archivado') and due_on<(now() at time zone 'America/Lima')::date)
) from public.cases $$;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('expedientes','expedientes',false,10485760,array['application/pdf','image/png','image/jpeg'])
on conflict(id) do nothing;
create policy municipal_files_read on storage.objects for select to authenticated
 using(bucket_id='expedientes' and private.document_access(name,false));
create policy municipal_files_insert on storage.objects for insert to authenticated
 with check(bucket_id='expedientes' and private.document_access(name,true));
create policy documents_staff_insert on public.case_documents for insert to authenticated
 with check(created_by=(select auth.uid()) and private.can_write_case(case_id)
 and exists(select 1 from storage.objects o where o.bucket_id='expedientes' and o.name=object_path
   and o.owner_id=(select auth.uid())::text));

create function private.log_document() returns trigger language plpgsql security definer set search_path = ''
as $$
  declare actor public.staff_profiles; target public.cases;
  begin
    if auth.uid() is null or new.created_by<>auth.uid() or not private.can_write_case(new.case_id) then
      raise exception 'No se permite registrar este adjunto.'; end if;
    select * into actor from public.staff_profiles where user_id=auth.uid() and is_active;
    select * into target from public.cases where id=new.case_id;
    insert into public.case_events(case_id,action,actor_id,actor_name,from_status,to_status,from_department_id,to_department_id,note)
      values(target.id,'adjunto',auth.uid(),actor.display_name,target.status,target.status,target.department_id,target.department_id,
             'Documento adjuntado: ' || new.file_name);
    return new;
  end
$$;
create trigger record_document after insert on public.case_documents for each row execute function private.log_document();

revoke all on public.municipal_settings,public.departments,public.staff_profiles,public.procedures,
 public.applicants,public.cases,public.case_events,public.case_documents from anon,authenticated;
grant select on public.municipal_settings,public.departments,public.staff_profiles,public.procedures,
 public.applicants,public.cases,public.case_events,public.case_documents to authenticated;
grant insert(id,case_id,file_name,object_path,media_type,size_bytes,sha256,created_by) on public.case_documents to authenticated;
revoke all on private.case_counters from public,anon,authenticated;
revoke execute on all functions in schema private from public,anon,authenticated;
grant execute on function private.staff_role(),private.can_read_case(uuid),private.can_write_case(uuid),
 private.document_access(text,boolean),private.register_case(jsonb),private.advance_case(uuid,integer,text,uuid,text) to authenticated;
revoke execute on function public.register_case(jsonb),public.advance_case(uuid,integer,text,uuid,text),public.case_metrics() from public,anon;
grant execute on function public.register_case(jsonb),public.advance_case(uuid,integer,text,uuid,text),public.case_metrics() to authenticated;
-- El event trigger interno no requiere invocación desde clientes de la API.
do $$ begin
 if to_regprocedure('public.rls_auto_enable()') is not null then
   revoke execute on function public.rls_auto_enable() from public,anon,authenticated;
 end if;
end $$;
commit;
