# Configuración para la Municipalidad Provincial de Chiclayo

Entidad indicada por el responsable del proyecto: **Municipalidad Provincial de Chiclayo (MPCH)**. Revisión de fuentes públicas: **16 de septiembre de 2026**. Nombre del piloto: **MuniGest Chiclayo**.

## Qué se configuró

La base municipal `lxvmwjcqdjoidgpinmgm` identifica a la MPCH, usa `America/Lima` y conserva las referencias del organigrama y TUPA. El login, la navegación y la demostración muestran Chiclayo. El catálogo ofrece enlaces a las fuentes oficiales.

Se incorporaron catorce gerencias presentes en el organigrama publicado de 2024 y contrastadas con la página de organización institucional. Son destinos iniciales para practicar la derivación; no representan todo el organigrama, sus subgerencias ni sus relaciones jerárquicas.

| Código interno | Destino |
|---|---|
| GM | Gerencia Municipal |
| GSG | Gerencia de Secretaría General |
| GAF | Gerencia de Administración y Finanzas |
| GRH | Gerencia de Recursos Humanos |
| GTIE | Gerencia de Tecnologías de la Información y Estadística |
| GAJ | Gerencia de Asesoría Jurídica |
| GPPM | Gerencia de Planeamiento, Presupuesto y Modernización |
| GDU | Gerencia de Desarrollo Urbano |
| GIP | Gerencia de Infraestructura Pública |
| GDSPF | Gerencia de Desarrollo Social y Promoción de la Familia |
| GDVT | Gerencia de Desarrollo Vial y Transportes |
| GSCF | Gerencia de Seguridad Ciudadana y Fiscalización |
| GDEL | Gerencia de Desarrollo Económico Local |
| GDA | Gerencia de Desarrollo Ambiental |
| MP | Mesa de Partes: punto de recepción del piloto |

`MP` es un destino operativo del piloto, no una gerencia atribuida al ROF. Los códigos son propios de MuniGest y no deben usarse como identificadores de integración con el SGD. El destino genérico `AC` se desactivó porque no se verificó una unidad con ese nombre en el organigrama consultado; no se borró su identificador ni sus relaciones. Se conservaron los identificadores existentes de `MP` y `GM`.

Cada área almacena su tipo y URL de referencia. La demostración usa la misma selección de áreas, con solicitudes ficticias de obras, licencias, residuos, documentación y programas sociales. Ninguna de esas solicitudes se inserta en Supabase.

## Sistemas que ya existen en Chiclayo

El [portal de servicios digitales de la MPCH](https://www.munichiclayo.gob.pe/serviciosonline/) enlaza mesa de partes virtual, consulta de expedientes SGD, verificación documental, casilla electrónica y pagos mediante VirtualSATCH, entre otros servicios. Se consultaron sus páginas públicas sin registrar solicitudes ni consultar expedientes de personas.

MuniGest queda como **piloto de gestión interna**. Sus códigos `EXP-...` son internos. No se ha implementado sincronización con esos sistemas y los botones del catálogo solo abren sus sitios. La incorporación al trabajo institucional requiere acordar con la MPCH el flujo concreto y cómo intercambiar registros con el SGD existente.

Para esa integración, el trabajo pendiente es documentar el contrato de API o exportación que facilite la entidad, mapear sus identificadores de áreas y expedientes, y establecer idempotencia y trazabilidad de la importación. No se presupone que exista una API pública de escritura ni se utiliza extracción de expedientes como sustituto de una integración acordada.

## TUPA y configuración pendiente

La publicación [TUPA vigente 2026](https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/7664214-texto-unico-de-procedimientos-administrativos-tupa-vigente-2026), del 27 de enero de 2026, refiere la Ordenanza Municipal N.º 000030-2025-MPCH/A e incluye el anexo extraído del SUT. En esta entrega se verificó la publicación y sus enlaces; no se transcribieron ni validaron individualmente sus fichas.

El catálogo conserva **Solicitud general**, marcada como referencia operativa, sin tarifa ni plazo legal. Para cargar un trámite se necesita su ficha, código, órgano competente, requisitos, derecho de tramitación, plazo, base normativa y versión vigente, contrastados por el área responsable. La fecha objetivo actual sigue siendo interna.

`municipal_settings.configured` permanece en `false`: registra que faltan la conformidad operativa, responsables y catálogo revisado, aunque la identidad institucional ya esté cargada. El ubigeo permanece sin asignar hasta validar la sede y el significado del campo; el código distrital de una sede no representa por sí solo toda la jurisdicción provincial.

## Fuentes y alcance de la revisión

| Fuente oficial | Uso en esta entrega |
|---|---|
| [Organigrama publicado de 2024](https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/6924346-organigrama-2024) | PDF revisado visualmente; nombres de las gerencias. La publicación refiere la O.M. N.º 0005-2024-MPCH-A. |
| [Organización institucional](https://www.gob.pe/institucion/munichiclayo/organizacion) | Contraste de nombres y descripción general de funciones. |
| [Compendio ROF](https://www.gob.pe/institucion/munichiclayo/colecciones/25691-reglamento-de-organizacion-y-funciones-rof) | Identificación de documentos y modificaciones publicadas. No se certificó un texto consolidado de todas las modificaciones. |
| [TUPA 2026](https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/7664214-texto-unico-de-procedimientos-administrativos-tupa-vigente-2026) | Referencia para la futura validación del catálogo. |
| [Mesa de partes virtual](https://www.munichiclayo.gob.pe/mpv/) y [consultas SGD](https://www.munichiclayo.gob.pe/CONSULTAS_SGD/) | Confirmación de canales existentes que deben considerarse en la integración. |

La fecha de consulta de una fuente no equivale a certificación de vigencia normativa ni a conformidad municipal del software. Las fuentes quedan identificadas para que el equipo municipal pueda contrastar cambios posteriores.
