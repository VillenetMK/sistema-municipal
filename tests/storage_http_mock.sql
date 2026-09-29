-- SOLO PostgreSQL de pruebas. Sustituye únicamente el transporte HTTP, no la autorización.
do $$ begin
  if exists(select 1 from information_schema.columns where table_schema='auth'
    and table_name='users' and column_name='encrypted_password') then
    raise exception 'El doble HTTP nunca se instala en Supabase real.';
  end if;
end $$;
create schema test_support;
create table test_support.document_bytes(path text primary key,content bytea not null,status integer not null default 200);
grant usage on schema test_support to authenticated;
grant select,insert,update,delete on test_support.document_bytes to authenticated;
create or replace function extensions.http(request extensions.http_request)
returns extensions.http_response language plpgsql security definer set search_path='' as $$
declare object_name text; content bytea; status_value integer;
begin
  if request.method::text<>'GET' or request.uri not like
    'https://lxvmwjcqdjoidgpinmgm.supabase.co/storage/v1/object/authenticated/expedientes/%' then
    raise exception 'Unexpected HTTP target in test'; end if;
  if not exists(select 1 from unnest(request.headers) h where h.field='Authorization' and h.value='Bearer test-session-token')
    or exists(select 1 from unnest(request.headers) h where lower(h.field)='apikey') then
    raise exception 'Missing authentication forwarding'; end if;
  object_name:=substring(request.uri from length('https://lxvmwjcqdjoidgpinmgm.supabase.co/storage/v1/object/authenticated/expedientes/')+1);
  select b.content,b.status into content,status_value from test_support.document_bytes b where b.path=object_name;
  return row(coalesce(status_value,404),'application/octet-stream',array[]::extensions.http_header[],
    extensions.bytea_to_text(content))::extensions.http_response;
end $$;
revoke execute on function extensions.http(extensions.http_request) from public,anon,authenticated;
