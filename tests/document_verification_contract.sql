-- Transporte simulado en tests/storage_http_mock.sql; validación y RLS reales.
begin;
insert into auth.users(id) values('dddddddd-0000-4000-8000-000000000001');
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
select 'dddddddd-0000-4000-8000-000000000001','Admin documentos','admin',id,true from public.departments where code='MP';
set local role authenticated;
select set_config('request.jwt.claim.sub','dddddddd-0000-4000-8000-000000000001',true);
select set_config('request.headers','{"authorization":"Bearer test-session-token","apikey":"sb_publishable_test_key_only"}',true);
do $$ declare target jsonb; content bytea; meta jsonb; result jsonb; object_name text; invalid jsonb;
begin
  target:=public.register_case(jsonb_build_object('request_id',gen_random_uuid(),
    'department_id',(select id from public.departments where code='MP'),'document_type','DNI','document_number','00000088',
    'applicant_name','Persona ficticia documentos','title','Expediente para validar adjuntos',
    'description','Documentos ficticios de pruebas aisladas y reversibles.','priority','normal','channel','presencial'));
  content:=decode('89504e470d0a1a0a0001020300ff','hex');
  object_name:=target->>'id'||'/dddddddd-0000-4000-8000-000000000002.png';
  insert into storage.objects(bucket_id,name,owner_id) values('expedientes',object_name,auth.uid()::text);
  insert into test_support.document_bytes(path,content) values(object_name,content);
  meta:=jsonb_build_object('id','dddddddd-0000-4000-8000-000000000002','case_id',target->>'id',
    'file_name','prueba.png','object_path',object_name,'media_type','image/png',
    'size_bytes',octet_length(content),'sha256',encode(sha256(content),'hex'));
  for invalid in select value from jsonb_array_elements(jsonb_build_array(
    meta||'{"size_bytes":1}',meta||jsonb_build_object('sha256',repeat('0',64)),
    meta||'{"media_type":"application/pdf"}',meta||'{"file_name":"engaño.pdf"}')) loop
    begin perform public.finalize_document(invalid); raise exception 'INVALID_BYTES_ACCEPTED';
    exception when raise_exception then if sqlerrm='INVALID_BYTES_ACCEPTED' then raise; end if; end;
  end loop;
  if (select count(*) from public.case_documents)<>0 then raise exception 'Documento inválido persistido'; end if;
  perform set_config('request.headers','{}',true);
  begin perform public.finalize_document(meta); raise exception 'NO_SESSION_ACCEPTED';
  exception when raise_exception then if sqlerrm='NO_SESSION_ACCEPTED' then raise; end if; end;
  perform set_config('request.headers','{"authorization":"Bearer test-session-token","apikey":"sb_publishable_test_key_only"}',true);
  update test_support.document_bytes set status=404 where path=object_name;
  begin perform public.finalize_document(meta); raise exception 'MISSING_STORAGE_ACCEPTED';
  exception when raise_exception then if sqlerrm='MISSING_STORAGE_ACCEPTED' then raise; end if; end;
  update test_support.document_bytes set status=200 where path=object_name;
  result:=public.finalize_document(meta);
  if result->>'verified_at' is null or result->>'sha256'<>encode(sha256(content),'hex') then
    raise exception 'No se verificaron los bytes binarios'; end if;
  if public.finalize_document(meta)->>'id'<>result->>'id'
    or (select count(*) from public.case_documents)<>1
    or (select count(*) from public.case_events where action='adjunto')<>1 then
    raise exception 'La finalización no es idempotente'; end if;
  if (public.database_health()->>'unverified_documents')::integer<>0 then raise exception 'Diagnóstico incorrecto'; end if;
end $$;
reset role;
rollback;
