-- Datos exclusivamente ficticios para verificar recuperación en PostgreSQL local.
alter table auth.users add column phone text;
create table auth.identities(id uuid primary key,user_id uuid references auth.users(id),provider text,identity_data jsonb);
create table auth.mfa_factors(id uuid primary key);
create schema supabase_migrations;
create table supabase_migrations.schema_migrations(version text,name text);
insert into auth.users(id,email) values ('cccccccc-0000-4000-8000-000000000001','backup@example.test');
insert into auth.identities values ('cccccccc-0000-4000-8000-000000000002','cccccccc-0000-4000-8000-000000000001','email','{}');
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
 select 'cccccccc-0000-4000-8000-000000000001','Prueba de restauración','admin',id,true from public.departments where code='MP';
select set_config('request.jwt.claim.sub','cccccccc-0000-4000-8000-000000000001',false);
do $$
declare result jsonb; object_name text; content bytea;
begin
 result:=public.register_case(jsonb_build_object('request_id','cccccccc-0000-4000-8000-000000000003',
 'department_id',(select id from public.departments where code='MP'),'document_type','DNI','document_number','00000001',
 'applicant_name','Solicitante ficticio de respaldo','email','','phone','','title','Ensayo local de restauración',
 'description','Este expediente solo existe en la base de pruebas aislada.','priority','normal','channel','presencial'));
 object_name:=result->>'id'||'/cccccccc-0000-4000-8000-000000000004.pdf';
 content:=convert_to(E'%PDF-1.7\nAdjunto ficticio del ensayo de respaldo.\n','UTF8');
 insert into storage.objects(bucket_id,name,owner_id) values('expedientes',object_name,'cccccccc-0000-4000-8000-000000000001');
 insert into public.case_documents(id,case_id,file_name,object_path,media_type,size_bytes,sha256,created_by)
 values('cccccccc-0000-4000-8000-000000000004',(result->>'id')::uuid,'ensayo.pdf',object_name,'application/pdf',length(content),
 encode(sha256(content),'hex'),'cccccccc-0000-4000-8000-000000000001');
end $$;
