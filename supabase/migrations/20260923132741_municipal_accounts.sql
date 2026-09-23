-- Invitaciones autorizadas en servidor; ningún rol se toma de user_metadata.
begin;
create table private.staff_invitations (
  id uuid primary key,
  email text not null check (email=lower(trim(email)) and length(email)<=254),
  display_name text not null check (length(trim(display_name)) between 3 and 120),
  role text not null check (role in ('admin','mesa_partes','gestor','consulta')),
  department_id uuid not null references public.departments(id),
  token_hash text not null unique,
  created_by uuid not null references public.staff_profiles(user_id),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default now()+interval '48 hours',
  claimed_by uuid references auth.users(id),
  claimed_at timestamptz,
  revoked_at timestamptz
);
create index staff_invitations_email_idx on private.staff_invitations(email);
create index staff_invitations_creator_idx on private.staff_invitations(created_by);
create index staff_invitations_department_idx on private.staff_invitations(department_id);
create index staff_invitations_claimed_idx on private.staff_invitations(claimed_by);
alter table private.staff_invitations enable row level security;
revoke all on private.staff_invitations from public,anon,authenticated;
alter table public.admin_events drop constraint admin_events_entity_check;
alter table public.admin_events add constraint admin_events_entity_check
  check (entity in ('departments','procedures','staff_profiles','staff_invitations'));

create function private.admin_invitations(operation text,payload jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$
declare actor public.staff_profiles; invitation private.staff_invitations; result jsonb; data jsonb;
  target uuid; email_value text; hash_value text; start_index integer;
begin
  perform pg_catalog.pg_advisory_xact_lock(716249103);
  select * into actor from public.staff_profiles where user_id=auth.uid() and is_active;
  if auth.uid() is null or actor.role is distinct from 'admin' then
    raise exception 'Solo un administrador activo puede administrar invitaciones.'; end if;
  if operation='list' then
    start_index:=coalesce((payload->>'offset')::integer,0);
    if start_index<0 then raise exception 'Página inválida.'; end if;
    select coalesce(jsonb_agg(to_jsonb(r) order by r.created_at desc,r.id),'[]') into result from (
      select id,email,display_name,role,department_id,created_at,expires_at,claimed_at,revoked_at
      from private.staff_invitations order by created_at desc,id limit 51 offset start_index
    ) r;
    return result;
  end if;
  if coalesce(length(trim(payload->>'reason')),0) not between 10 and 500 then
    raise exception 'Registra un motivo de 10 a 500 caracteres.'; end if;
  target:=(payload->>'id')::uuid;
  if target is null then raise exception 'Falta el identificador de invitación.'; end if;
  select * into invitation from private.staff_invitations where id=target for update;
  if operation='create' then
    email_value:=lower(trim(payload->>'email'));
    if email_value is null or length(email_value)>254 or email_value !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
      or email_value ~ '\.(invalid|test|example)$' then raise exception 'Escribe un correo real.'; end if;
    if coalesce(payload->>'token','') !~ '^[a-f0-9]{64}$' then raise exception 'Código de invitación inválido.'; end if;
    hash_value:=encode(sha256(convert_to(payload->>'token','UTF8')),'hex');
    if invitation.id is not null then
      if invitation.email=email_value and invitation.token_hash=hash_value
        and invitation.display_name=trim(payload->>'display_name') and invitation.role=payload->>'role'
        and invitation.department_id=(payload->>'department_id')::uuid and invitation.created_by=actor.user_id then
        return to_jsonb(invitation)-'token_hash';
      end if;
      raise exception 'El identificador ya corresponde a otra invitación.';
    end if;
    if exists(select 1 from auth.users where lower(email)=email_value) then
      raise exception 'Este correo ya tiene una cuenta. Revisa su perfil o recupera su contraseña.'; end if;
    if exists(select 1 from private.staff_invitations where email=email_value and claimed_at is null
      and revoked_at is null and expires_at>now()) then
      raise exception 'Ya existe una invitación pendiente. Revócala antes de crear otra.'; end if;
    perform 1 from public.departments where id=(payload->>'department_id')::uuid and is_active for share;
    if not found then raise exception 'Selecciona un área activa.'; end if;
    insert into private.staff_invitations(id,email,display_name,role,department_id,token_hash,created_by)
      values(target,email_value,trim(payload->>'display_name'),payload->>'role',
        (payload->>'department_id')::uuid,hash_value,actor.user_id) returning * into invitation;
  elsif operation='revoke' then
    if invitation.id is null then raise exception 'No existe la invitación.'; end if;
    if invitation.claimed_at is not null then raise exception 'La cuenta ya fue creada. Edita su perfil para desactivarla.'; end if;
    if invitation.revoked_at is not null then return to_jsonb(invitation)-'token_hash'; end if;
    data:=to_jsonb(invitation)-'token_hash';
    update private.staff_invitations set revoked_at=now() where id=target returning * into invitation;
  else raise exception 'Operación inválida.';
  end if;
  result:=to_jsonb(invitation)-'token_hash';
  insert into public.admin_events(entity,record_id,actor_id,actor_name,reason,before_data,after_data)
    values('staff_invitations',target,actor.user_id,actor.display_name,trim(payload->>'reason'),data,result);
  return result;
end $$;

create function private.accept_staff_invitation() returns trigger
language plpgsql security definer set search_path='' as $$
declare invitation private.staff_invitations; code text;
begin
  code:=new.raw_user_meta_data->>'municipal_invitation';
  -- Auth sin invitación no obtiene perfil municipal. Conserva el alta administrativa existente.
  if code is null then return new; end if;
  perform pg_catalog.pg_advisory_xact_lock(716249103);
  if code !~ '^[a-f0-9]{64}$' then raise exception 'Invitación inválida.'; end if;
  select * into invitation from private.staff_invitations
    where token_hash=encode(sha256(convert_to(code,'UTF8')),'hex') for update;
  if invitation.id is null or invitation.email is distinct from lower(new.email)
    or invitation.claimed_at is not null or invitation.revoked_at is not null or invitation.expires_at<=now() then
    raise exception 'La invitación no es válida para este correo o ha vencido.'; end if;
  if not exists(select 1 from public.staff_profiles where user_id=invitation.created_by and role='admin' and is_active) then
    raise exception 'El administrador de la invitación ya no está autorizado.'; end if;
  insert into public.staff_profiles(user_id,display_name,role,department_id,is_active)
    values(new.id,invitation.display_name,invitation.role,invitation.department_id,true);
  update private.staff_invitations set claimed_by=new.id,claimed_at=now() where id=invitation.id;
  update auth.users set raw_user_meta_data=raw_user_meta_data-'municipal_invitation' where id=new.id;
  insert into public.admin_events(entity,record_id,actor_id,actor_name,reason,after_data)
    select 'staff_profiles',new.id,p.user_id,p.display_name,'Activación mediante invitación autorizada',
      jsonb_build_object('invitation_id',invitation.id,'role',invitation.role,'department_id',invitation.department_id)
    from public.staff_profiles p where p.user_id=invitation.created_by;
  return new;
end $$;
create trigger municipal_accept_invitation after insert on auth.users
  for each row execute function private.accept_staff_invitation();
create function public.admin_invitations(operation text,payload jsonb default '{}') returns jsonb
language sql security invoker set search_path='' as $$ select private.admin_invitations(operation,payload) $$;
revoke all on function private.accept_staff_invitation() from public,anon,authenticated;
revoke all on function private.admin_invitations(text,jsonb),public.admin_invitations(text,jsonb) from public,anon;
grant execute on function private.admin_invitations(text,jsonb),public.admin_invitations(text,jsonb) to authenticated;
commit;
