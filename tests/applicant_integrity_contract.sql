-- Datos ficticios, transacción revertida y sin red.
begin;
insert into auth.users(id) values ('eeeeeeee-0000-4000-8000-000000000001'),('eeeeeeee-0000-4000-8000-000000000002');
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
select 'eeeeeeee-0000-4000-8000-000000000001','Admin solicitantes','admin',id,true from public.departments where code='MP';
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
select 'eeeeeeee-0000-4000-8000-000000000002','Consulta solicitantes','consulta',id,true from public.departments where code='MP';
set local role authenticated;
select set_config('request.jwt.claim.sub','eeeeeeee-0000-4000-8000-000000000001',true);
do $$ declare payload jsonb; first_case jsonb; second_case jsonb; person jsonb; corrected jsonb; receipt jsonb; begin
  payload:=jsonb_build_object('request_id',gen_random_uuid(),'department_id',(select id from public.departments where code='MP'),
    'document_type','DNI','document_number','00000077','applicant_name','Persona ficticia original',
    'email','original@example.test','phone','999000111','title','Primera solicitud de prueba',
    'description','Solicitud ficticia para verificar la conservación histórica.','priority','normal','channel','presencial');
  first_case:=public.register_case(payload);
  second_case:=public.register_case(payload||jsonb_build_object('request_id',gen_random_uuid(),'email','nuevo@example.test','phone','999000222'));
  if (first_case->'applicant_snapshot'->>'email')<>'original@example.test'
    or (second_case->'applicant_snapshot'->>'email')<>'nuevo@example.test'
    or (second_case->'applicant_snapshot'->>'phone')<>'999000222'
    or (select count(*) from public.applicants)<>1 then raise exception 'Contactos por solicitud incorrectos'; end if;
  if (public.register_case(payload)->>'id')<>first_case->>'id' then raise exception 'Idempotencia alterada'; end if;
  person:=public.admin_list_records('applicants','00000077',0)->0;
  if person is null then raise exception 'Solicitante no aparece en Administración'; end if;
  corrected:=public.admin_save_record('applicants',person||'{"full_name":"Persona ficticia corregida","email":"corregido@example.test"}',1,'Corrección ficticia contrastada para este ensayo.');
  if corrected->>'version'<>'2' then raise exception 'Versión no incrementada'; end if;
  receipt:=public.case_receipt((first_case->>'id')::uuid);
  if receipt->'case'->'applicant'->>'full_name'<>'Persona ficticia original' then raise exception 'Constancia histórica alterada'; end if;
  if (select count(*) from public.admin_events where entity='applicants')<>1 then raise exception 'Corrección sin auditoría'; end if;
  begin
    perform public.admin_save_record('applicants',person||'{"email":"otro@example.test"}',1,'Intento con una versión desactualizada.');
    raise exception 'STALE_APPLICANT_ACCEPTED';
  exception when raise_exception then if sqlerrm='STALE_APPLICANT_ACCEPTED' then raise; end if; end;
  perform set_config('test.applicant',person::text,true);
  perform set_config('request.jwt.claim.sub','eeeeeeee-0000-4000-8000-000000000002',true);
  begin
    perform public.admin_save_record('applicants',corrected||'{"email":"sinpermiso@example.test"}',2,'Corrección desde un perfil no autorizado.');
    raise exception 'UNAUTHORIZED_APPLICANT_ACCEPTED';
  exception when raise_exception then if sqlerrm='UNAUTHORIZED_APPLICANT_ACCEPTED' then raise; end if; end;
end $$;
reset role;
do $$ begin
  begin update public.cases set applicant_snapshot=applicant_snapshot||'{"email":"alterado@example.test"}';
    raise exception 'SNAPSHOT_REWRITTEN';
  exception when raise_exception then if sqlerrm='SNAPSHOT_REWRITTEN' then raise; end if; end;
end $$;
rollback;
