-- SOLO EN UNA BASE LOCAL DE PRUEBAS. Todos los datos se revierten al finalizar.
begin;
insert into auth.users(id) values
 ('aaaaaaaa-0000-4000-8000-000000000001'),('aaaaaaaa-0000-4000-8000-000000000002'),
 ('aaaaaaaa-0000-4000-8000-000000000003'),('aaaaaaaa-0000-4000-8000-000000000004'),
 ('aaaaaaaa-0000-4000-8000-000000000005');
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
 select 'aaaaaaaa-0000-4000-8000-000000000001','Admin de prueba','admin',id,true from public.departments where code='MP';
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
 select 'aaaaaaaa-0000-4000-8000-000000000002','Gestor área MP','gestor',id,true from public.departments where code='MP';
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
 select 'aaaaaaaa-0000-4000-8000-000000000003','Gestor otra área','gestor',id,true from public.departments where code='GM';
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
 select 'aaaaaaaa-0000-4000-8000-000000000004','Consulta de prueba','consulta',id,true from public.departments where code='MP';
insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
 select 'aaaaaaaa-0000-4000-8000-000000000005','Desactivado de prueba','admin',id,false from public.departments where code='MP';

set local role authenticated;
select set_config('request.jwt.claim.sub','aaaaaaaa-0000-4000-8000-000000000001',true);
do $$
declare payload jsonb; result jsonb; repeat_result jsonb; count_events integer;
begin
 payload := jsonb_build_object('request_id','bbbbbbbb-0000-4000-8000-000000000001','department_id',(select id from public.departments where code='MP'),
   'document_type','DNI','document_number','00000001','applicant_name','Persona de prueba','email','','phone','',
   'title','Expediente de prueba','description','Descripción de solicitud para pruebas locales.',
   'priority','normal','channel','presencial','due_on',null);
 result:=public.register_case(payload);
 repeat_result:=public.register_case(payload);
 if result->>'id' <> repeat_result->>'id' or (select count(*) from public.cases)<>1 then raise exception 'Idempotencia falló'; end if;
 begin
   perform public.register_case(payload || '{"title":"Cambio en un intento ya utilizado"}'::jsonb);
   raise exception 'IDEMPOTENCY_BYPASS';
 exception when raise_exception then if sqlerrm='IDEMPOTENCY_BYPASS' then raise; end if; end;
 perform set_config('test.case_id',result->>'id',true);
 begin
   update public.staff_profiles set role='admin';
   raise exception 'ROLE_ESCALATION';
 exception when insufficient_privilege then null; end;
 begin
   delete from public.case_events;
   raise exception 'AUDIT_DELETION';
 exception when insufficient_privilege then null; end;
 begin
   update public.cases set status='archivado';
   raise exception 'DIRECT_CASE_EDIT';
 exception when insufficient_privilege then null; end;
 perform public.advance_case((result->>'id')::uuid,1,'en_revision',(result->>'department_id')::uuid,'Inicio de revisión del documento.');
 begin
   perform public.advance_case((result->>'id')::uuid,1,'observado',(result->>'department_id')::uuid,'Intento con una versión ya obsoleta.');
   raise exception 'STALE_WRITE';
 exception when raise_exception then if sqlerrm='STALE_WRITE' then raise; end if; end;
 begin
   perform public.advance_case((result->>'id')::uuid,2,'archivado',(result->>'department_id')::uuid,'Intento de omitir la atención del expediente.');
   raise exception 'STATE_BYPASS';
 exception when raise_exception then if sqlerrm='STATE_BYPASS' then raise; end if; end;
 select count(*) into count_events from public.case_events;
 if count_events<>2 then raise exception 'Historial inconsistente'; end if;
end $$;

-- Simulación local de un objeto cargado y su metadata documental.
insert into storage.objects(bucket_id,name,owner_id)
 values('expedientes',current_setting('test.case_id') || '/cccccccc-0000-4000-8000-000000000001.pdf',auth.uid()::text);
insert into public.case_documents(id,case_id,file_name,object_path,media_type,size_bytes,sha256,created_by)
 values('cccccccc-0000-4000-8000-000000000001',current_setting('test.case_id')::uuid,'solicitud.pdf',
 current_setting('test.case_id') || '/cccccccc-0000-4000-8000-000000000001.pdf','application/pdf',100,repeat('0',64),auth.uid());
do $$ begin
 if (select count(*) from public.case_documents)<>1 then raise exception 'Adjunto no registrado'; end if;
 if (select count(*) from public.case_events)<>3 then raise exception 'Adjunto sin historial'; end if;
end $$;

select set_config('request.jwt.claim.sub','aaaaaaaa-0000-4000-8000-000000000003',true);
do $$ begin
 if (select count(*) from public.cases)<>0 or (select count(*) from public.applicants)<>0 or (select count(*) from public.case_events)<>0 or (select count(*) from public.case_documents)<>0 or (select count(*) from storage.objects)<>0 then raise exception 'Fuga entre áreas'; end if;
 begin
   perform public.advance_case(current_setting('test.case_id')::uuid,2,'atendido',(select id from public.departments where code='GM'),'Intento de actualización desde otra área.');
   raise exception 'CROSS_DEPARTMENT_WRITE';
 exception when raise_exception then if sqlerrm='CROSS_DEPARTMENT_WRITE' then raise; end if; end;
end $$;

select set_config('request.jwt.claim.sub','aaaaaaaa-0000-4000-8000-000000000004',true);
do $$ begin
 if (select count(*) from public.cases)<>1 then raise exception 'Consulta no puede leer su área'; end if;
 begin
   perform public.advance_case(current_setting('test.case_id')::uuid,2,'atendido',(select id from public.departments where code='MP'),'Intento de editar desde perfil de consulta.');
   raise exception 'READ_ONLY_WRITE';
 exception when raise_exception then if sqlerrm='READ_ONLY_WRITE' then raise; end if; end;
end $$;

select set_config('request.jwt.claim.sub','aaaaaaaa-0000-4000-8000-000000000005',true);
do $$ begin
 if (select count(*) from public.cases)<>0 or (select count(*) from public.staff_profiles)<>0 then raise exception 'Acceso de cuenta inactiva'; end if;
end $$;

select set_config('request.jwt.claim.sub','aaaaaaaa-0000-4000-8000-000000000002',true);
do $$ declare dept uuid; target uuid:=current_setting('test.case_id')::uuid; begin
 select id into dept from public.departments where code='MP';
 if (select count(*) from public.cases)<>1 then raise exception 'Gestor no ve su expediente'; end if;
 perform public.advance_case(target,2,'atendido',dept,'Respuesta registrada internamente para el expediente.');
 perform public.advance_case(target,3,'archivado',dept,'Expediente concluido y archivado para consulta.');
 if private.can_write_case(target) then raise exception 'Expediente archivado editable'; end if;
 if (select count(*) from public.case_events)<>5 then raise exception 'Falta una actuación en el historial'; end if;
end $$;
reset role;
set local role anon;
select set_config('request.jwt.claim.sub','',true);
do $$ begin
 begin perform * from public.cases; raise exception 'ANON_READ'; exception when insufficient_privilege then null; end;
 begin perform public.register_case('{}'); raise exception 'ANON_RPC'; exception when insufficient_privilege then null; end;
end $$;
reset role;
rollback;
