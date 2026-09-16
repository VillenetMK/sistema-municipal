-- Piloto MPCH. Fuentes públicas revisadas el 2026-09-16; docs/CHICLAYO.md.
-- Es una selección de destinos, no una declaración de implementación completa del ROF.
begin;

alter table public.municipal_settings
  add column official_website text,
  add column organization_source_url text,
  add column tupa_source_url text,
  add column sources_checked_on date;

update public.municipal_settings
set institution_name = 'Municipalidad Provincial de Chiclayo',
    timezone = 'America/Lima',
    configured = false,
    official_website = 'https://www.munichiclayo.gob.pe/serviciosonline/',
    organization_source_url = 'https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/6924346-organigrama-2024',
    tupa_source_url = 'https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/7664214-texto-unico-de-procedimientos-administrativos-tupa-vigente-2026',
    sources_checked_on = '2026-09-16'
where id = 1;

comment on column public.municipal_settings.configured is
  'Conformidad operativa del piloto: requiere validación municipal de áreas, usuarios y catálogo. Conocer el nombre de la entidad no implica esa conformidad.';

alter table public.departments
  add column unit_type text not null default 'referencia'
    check (unit_type in ('gerencia','punto_recepcion','referencia')),
  add column source_url text;

-- Conserva identificadores y relaciones de MP y GM.
insert into public.departments(code, name, unit_type, source_url) values
  ('GM', 'Gerencia Municipal', 'gerencia', null),
  ('GSG', 'Gerencia de Secretaría General', 'gerencia', null),
  ('GAF', 'Gerencia de Administración y Finanzas', 'gerencia', null),
  ('GRH', 'Gerencia de Recursos Humanos', 'gerencia', null),
  ('GTIE', 'Gerencia de Tecnologías de la Información y Estadística', 'gerencia', null),
  ('GAJ', 'Gerencia de Asesoría Jurídica', 'gerencia', null),
  ('GPPM', 'Gerencia de Planeamiento, Presupuesto y Modernización', 'gerencia', null),
  ('GDU', 'Gerencia de Desarrollo Urbano', 'gerencia', null),
  ('GIP', 'Gerencia de Infraestructura Pública', 'gerencia', null),
  ('GDSPF', 'Gerencia de Desarrollo Social y Promoción de la Familia', 'gerencia', null),
  ('GDVT', 'Gerencia de Desarrollo Vial y Transportes', 'gerencia', null),
  ('GSCF', 'Gerencia de Seguridad Ciudadana y Fiscalización', 'gerencia', null),
  ('GDEL', 'Gerencia de Desarrollo Económico Local', 'gerencia', null),
  ('GDA', 'Gerencia de Desarrollo Ambiental', 'gerencia', null)
on conflict (code) do update
set name = excluded.name, unit_type = excluded.unit_type;

update public.departments
set source_url = 'https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/6924346-organigrama-2024'
where code in ('GM','GSG','GAF','GRH','GTIE','GAJ','GPPM','GDU','GIP','GDSPF','GDVT','GSCF','GDEL','GDA');

update public.departments
set unit_type = 'punto_recepcion', source_url = 'https://www.munichiclayo.gob.pe/mpv/'
where code = 'MP';

-- El área genérica AC no figura con ese nombre en el organigrama consultado.
-- Se desactiva, sin borrar sus posibles relaciones ni historial.
update public.departments set is_active = false where code = 'AC';

-- No se importan requisitos, derechos de trámite, plazos ni procedimientos oficiales.
commit;
