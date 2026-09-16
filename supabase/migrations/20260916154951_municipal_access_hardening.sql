begin;
-- Contexto de área calculado una vez por consulta; favorece índices de department_id.
create function private.staff_department() returns uuid
language sql stable security definer set search_path = ''
as $$ select department_id from public.staff_profiles where user_id=auth.uid() and is_active and auth.uid() is not null $$;
revoke execute on function private.staff_department() from public,anon;
grant execute on function private.staff_department() to authenticated;
drop policy cases_staff_read on public.cases;
create policy cases_staff_read on public.cases for select to authenticated using (
 (select private.staff_role()) in ('admin','mesa_partes')
 or ((select private.staff_role()) in ('gestor','consulta') and department_id=(select private.staff_department()))
);
-- Denegación explícita para el contador; solo opera el propietario desde funciones internas.
create policy counters_no_client_access on private.case_counters for all to authenticated
 using(false) with check(false);

-- Serializar la metadata documental con los cambios de estado del expediente.
create or replace function private.log_document() returns trigger
language plpgsql security definer set search_path = ''
as $$
 declare actor public.staff_profiles; target public.cases;
 begin
   if auth.uid() is null or new.created_by<>auth.uid() then
     raise exception 'No se permite registrar este adjunto.'; end if;
   select * into actor from public.staff_profiles where user_id=auth.uid() and is_active;
   select * into target from public.cases where id=new.case_id for update;
   if target.id is null or target.status in ('atendido','archivado')
      or actor.role is null or actor.role not in ('admin','mesa_partes','gestor')
      or (actor.role='gestor' and actor.department_id is distinct from target.department_id) then
     raise exception 'El expediente se cerró o cambió de área. No se puede registrar el adjunto.'; end if;
   insert into public.case_events(case_id,action,actor_id,actor_name,from_status,to_status,from_department_id,to_department_id,note)
     values(target.id,'adjunto',auth.uid(),actor.display_name,target.status,target.status,target.department_id,target.department_id,
            'Documento adjuntado: ' || new.file_name);
   return new;
 end
$$;
revoke execute on function private.log_document() from public,anon,authenticated;
commit;
