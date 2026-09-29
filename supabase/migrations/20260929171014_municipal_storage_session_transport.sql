-- Storage autentica el JWT del usuario. El gateway REST elimina apikey.
-- Solo se reenvía Authorization al endpoint autenticado del proyecto municipal.
begin;
create or replace function private.fetch_document_bytes(object_path text) returns bytea
-- http 1.6 del proveedor limita por defecto la conexión a 1 s y la petición a 5 s.
-- No se modifican parámetros reservados del servicio administrado.
language plpgsql security definer set search_path='' as $$
declare headers jsonb; token text; response extensions.http_response;
begin
  if auth.uid() is null or not private.document_access(object_path,true) then
    raise exception 'No tienes permiso para verificar este documento.'; end if;
  headers:=nullif(current_setting('request.headers',true),'')::jsonb;
  token:=headers->>'authorization';
  if token is null or token !~ '^Bearer [A-Za-z0-9_.-]+$' or length(token)>16384 then
    raise exception 'No se pudo validar la sesión de carga. Actualiza la aplicación e inténtalo nuevamente.'; end if;
  -- Destino fijo y ruta restringida a UUID/extensión; nunca acepta URLs del usuario.
  select * into response from extensions.http((
    'GET','https://lxvmwjcqdjoidgpinmgm.supabase.co/storage/v1/object/authenticated/expedientes/'||object_path,
    array[row('Authorization',token)::extensions.http_header,
      row('Range','bytes=0-10485760')::extensions.http_header],null,null
  )::extensions.http_request);
  if response.status not in (200,206) then raise exception 'Storage no confirmó la lectura del archivo.'; end if;
  -- text_to_bytea preserva bytes NUL; content::bytea no es seguro para binarios.
  return extensions.text_to_bytea(response.content);
exception when others then
  raise exception 'No se pudo verificar el archivo en Storage. El adjunto no se confirmó; vuelve a intentarlo.';
end $$;
revoke all on function private.fetch_document_bytes(text) from public,anon,authenticated;

create or replace function private.database_health() returns jsonb
language plpgsql stable security definer set search_path='' as $$
begin
  if auth.uid() is null or private.staff_role() is distinct from 'admin' then
    raise exception 'Solo un administrador activo puede revisar la integridad.'; end if;
  return jsonb_build_object('checked_at',statement_timestamp(),
    'file_verification_ready',coalesce(
      (nullif(current_setting('request.headers',true),'')::jsonb->>'authorization') ~ '^Bearer [A-Za-z0-9_.-]+$',false),
    'documents_without_object',(select count(*) from public.case_documents d where not exists(
      select 1 from storage.objects o where o.bucket_id='expedientes' and o.name=d.object_path)),
    'unregistered_objects',(select count(*) from storage.objects o where o.bucket_id='expedientes'
      and o.created_at<now()-interval '1 hour' and not exists(select 1 from public.case_documents d where d.object_path=o.name)),
    'unverified_documents',(select count(*) from public.case_documents where verified_at is null),
    'unassigned_pending',(select count(*) from public.cases where status not in ('atendido','archivado') and assigned_to is null),
    'pending_without_target',(select count(*) from public.cases where status not in ('atendido','archivado') and due_on is null));
end $$;
commit;
