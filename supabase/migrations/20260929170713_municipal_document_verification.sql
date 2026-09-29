-- Verificación de los bytes de Storage: aplicación Python y reglas en PostgreSQL.
begin;
create schema if not exists extensions;
create extension if not exists http with schema extensions;
-- La extensión no es una API de red para clientes autenticados/anónimos.
do $$ declare f record; begin
  for f in select p.oid::regprocedure as signature from pg_proc p
    join pg_depend d on d.classid='pg_proc'::regclass and d.objid=p.oid and d.deptype='e'
    join pg_extension e on e.oid=d.refobjid where e.extname='http'
  loop execute format('revoke execute on function %s from public,anon,authenticated',f.signature); end loop;
end $$;

alter table public.case_documents add column verified_at timestamptz;
comment on column public.case_documents.verified_at is
  'Instante en que el servidor leyó los bytes de Storage y comprobó firma, tamaño y SHA-256. NULL identifica registros anteriores no verificados.';

create function private.fetch_document_bytes(object_path text) returns bytea
-- http 1.6 del proveedor limita por defecto la conexión a 1 s y la petición a 5 s.
-- No se modifican parámetros reservados del servicio administrado.
language plpgsql security definer set search_path='' as $$
declare headers jsonb; token text; api_key text; response extensions.http_response;
begin
  if auth.uid() is null or not private.document_access(object_path,true) then
    raise exception 'No tienes permiso para verificar este documento.'; end if;
  headers:=nullif(current_setting('request.headers',true),'')::jsonb;
  token:=headers->>'authorization'; api_key:=headers->>'apikey';
  if token is null or token !~ '^Bearer [A-Za-z0-9_.-]+$' or length(token)>16384
    or api_key is null or length(api_key) not between 20 and 2048 or api_key !~ '^[A-Za-z0-9_.-]+$' then
    raise exception 'No se pudo validar la sesión de carga. Actualiza la aplicación e inténtalo nuevamente.'; end if;
  -- Destino fijo y ruta restringida a UUID/extensión; nunca acepta URLs del usuario.
  select * into response from extensions.http((
    'GET','https://lxvmwjcqdjoidgpinmgm.supabase.co/storage/v1/object/authenticated/expedientes/'||object_path,
    array[row('Authorization',token)::extensions.http_header,row('apikey',api_key)::extensions.http_header,
      row('Range','bytes=0-10485760')::extensions.http_header],null,null
  )::extensions.http_request);
  if response.status not in (200,206) then raise exception 'Storage no confirmó la lectura del archivo.'; end if;
  -- text_to_bytea preserva bytes NUL; content::bytea no es seguro para binarios.
  return extensions.text_to_bytea(response.content);
exception when others then
  raise exception 'No se pudo verificar el archivo en Storage. El adjunto no se confirmó; vuelve a intentarlo.';
end $$;
revoke all on function private.fetch_document_bytes(text) from public,anon,authenticated;

create function private.verify_document_content() returns trigger
language plpgsql security definer set search_path='' as $$
declare content bytea; detected text; extension_value text;
begin
  if auth.uid() is null or new.created_by<>auth.uid() or not private.can_write_case(new.case_id)
    or new.object_path !~ ('^'||new.case_id::text||'/[0-9a-f-]{36}\.(pdf|png|jpg|jpeg)$') then
    raise exception 'No se permite registrar este adjunto.'; end if;
  if not exists(select 1 from storage.objects where bucket_id='expedientes'
    and name=new.object_path and owner_id=auth.uid()::text) then
    raise exception 'El archivo debe pertenecer a tu sesión de carga.'; end if;
  content:=private.fetch_document_bytes(new.object_path);
  if content is null or octet_length(content) not between 1 and 10485760 then
    raise exception 'El archivo debe contener datos y pesar como máximo 10 MB.'; end if;
  detected:=case
    when substring(content from 1 for 5)=decode('255044462d','hex') then 'application/pdf'
    when substring(content from 1 for 8)=decode('89504e470d0a1a0a','hex') then 'image/png'
    when substring(content from 1 for 3)=decode('ffd8ff','hex') then 'image/jpeg'
    else null end;
  extension_value:=lower(substring(new.file_name from '\.([^.]+)$'));
  if detected is null or detected<>new.media_type
    or (detected='application/pdf' and (extension_value is distinct from 'pdf' or new.object_path !~ '\.pdf$'))
    or (detected='image/png' and (extension_value is distinct from 'png' or new.object_path !~ '\.png$'))
    or (detected='image/jpeg' and (extension_value is null or extension_value not in ('jpg','jpeg') or new.object_path !~ '\.(jpg|jpeg)$')) then
    raise exception 'El contenido, la extensión y el tipo del archivo no coinciden.'; end if;
  if new.size_bytes is distinct from octet_length(content)::bigint
    or new.sha256 is distinct from encode(sha256(content),'hex') then
    raise exception 'El tamaño o la huella del archivo no coinciden con el contenido guardado.'; end if;
  new.verified_at:=statement_timestamp();
  return new;
end $$;
create trigger documents_verify_content before insert on public.case_documents
for each row execute function private.verify_document_content();
revoke all on function private.verify_document_content() from public,anon,authenticated;

create function private.finalize_document(metadata jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$
declare existing public.case_documents; target uuid; object_name text;
begin
  target:=(metadata->>'case_id')::uuid; object_name:=metadata->>'object_path';
  if auth.uid() is null or not private.can_read_case(target) then
    raise exception 'El expediente no está disponible para tu área.'; end if;
  if coalesce(length(object_name),0) not between 73 and 80 then raise exception 'Ruta documental inválida.'; end if;
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended('document:'||object_name,0));
  select * into existing from public.case_documents where object_path=object_name;
  if existing.id is not null then
    if existing.created_by=auth.uid() and existing.case_id=target
      and existing.id=(metadata->>'id')::uuid and existing.file_name=metadata->>'file_name'
      and existing.media_type=metadata->>'media_type' and existing.size_bytes=(metadata->>'size_bytes')::bigint
      and existing.sha256=metadata->>'sha256' then return to_jsonb(existing); end if;
    raise exception 'Esta carga ya se registró con otros datos.';
  end if;
  if not private.can_write_case(target) then raise exception 'El expediente ya no admite adjuntos.'; end if;
  insert into public.case_documents(id,case_id,file_name,object_path,media_type,size_bytes,sha256,created_by)
    values((metadata->>'id')::uuid,target,metadata->>'file_name',object_name,metadata->>'media_type',
      (metadata->>'size_bytes')::bigint,metadata->>'sha256',auth.uid()) returning * into existing;
  return to_jsonb(existing);
end $$;
create function public.finalize_document(metadata jsonb) returns jsonb
language sql security invoker set search_path='' as $$ select private.finalize_document(metadata) $$;
revoke all on function private.finalize_document(jsonb),public.finalize_document(jsonb) from public,anon;
grant execute on function private.finalize_document(jsonb),public.finalize_document(jsonb) to authenticated;

create function private.database_health() returns jsonb
language plpgsql stable security definer set search_path='' as $$
begin
  if auth.uid() is null or private.staff_role() is distinct from 'admin' then
    raise exception 'Solo un administrador activo puede revisar la integridad.'; end if;
  return jsonb_build_object('checked_at',statement_timestamp(),
    'file_verification_ready',coalesce(
      (nullif(current_setting('request.headers',true),'')::jsonb->>'authorization') ~ '^Bearer [A-Za-z0-9_.-]+$'
      and (nullif(current_setting('request.headers',true),'')::jsonb->>'apikey') ~ '^[A-Za-z0-9_.-]+$',false),
    'documents_without_object',(select count(*) from public.case_documents d where not exists(
      select 1 from storage.objects o where o.bucket_id='expedientes' and o.name=d.object_path)),
    'unregistered_objects',(select count(*) from storage.objects o where o.bucket_id='expedientes'
      and o.created_at<now()-interval '1 hour' and not exists(select 1 from public.case_documents d where d.object_path=o.name)),
    'unverified_documents',(select count(*) from public.case_documents where verified_at is null),
    'unassigned_pending',(select count(*) from public.cases where status not in ('atendido','archivado') and assigned_to is null),
    'pending_without_target',(select count(*) from public.cases where status not in ('atendido','archivado') and due_on is null));
end $$;
create function public.database_health() returns jsonb language sql stable security invoker set search_path=''
as $$ select private.database_health() $$;
revoke all on function private.database_health(),public.database_health() from public,anon;
grant execute on function private.database_health(),public.database_health() to authenticated;
commit;
