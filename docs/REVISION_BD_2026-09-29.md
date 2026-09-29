# Revisión de la base de datos — 29 de septiembre de 2026

## Resultado

La base actual es coherente con el alcance del piloto de Mesa de Partes y seguimiento de expedientes. Los controles revisados de acceso e integridad dieron el resultado esperado. La prioridad es corregir el tratamiento de datos de contacto, reforzar la verificación documental y cerrar la operación de respaldos antes de ampliar módulos.

Proyecto revisado: `lxvmwjcqdjoidgpinmgm`, identificado en `municipal_settings` como **Municipalidad Provincial de Chiclayo** y con estado `ACTIVE_HEALTHY`. Referencia de código: `35397572ede34e587c06291522349282acc4ab55`. Este proyecto es el piloto MuniGest; no constituye acceso a la base institucional de la MPCH. No se consultó EcoSphere.

La revisión de la base alojada fue de **solo lectura**. No se modificaron datos, permisos, cuentas, contraseñas ni esquema. No se copiaron identidades, contactos ni contenido de expedientes a este informe.

## Inventario comprobado

Se cuentan únicamente las tablas de la aplicación; se excluyen las tablas gestionadas de Auth, Storage y otros servicios de Supabase.

| Tabla | Función | Registros |
|---|---|---:|
| `public.municipal_settings` | Identidad y configuración institucional | 1 |
| `public.departments` | Áreas de destino | 16, de las cuales 15 activas |
| `public.staff_profiles` | Personal y permisos | 4, todos activos |
| `public.procedures` | Catálogo de trámites | 1, de referencia |
| `public.applicants` | Solicitantes | 1 |
| `public.cases` | Expedientes | 1 |
| `public.case_events` | Historial de expedientes | 1 |
| `public.case_documents` | Fichas de adjuntos | 0 |
| `public.admin_events` | Historial administrativo | 1 |
| `private.case_counters` | Numeración anual | 1 |
| `private.staff_invitations` | Invitaciones de personal | 0 |

Son **11 tablas: 9 públicas y 2 privadas**. Las siete migraciones de GitHub figuran aplicadas. Las 11 tablas tienen clave primaria y RLS activado. Las 18 claves foráneas tienen un índice que comienza por sus columnas; no se detectaron índices inválidos ni restricciones pendientes de validar.

El único expediente está en estado `recibido`, tiene trámite asignado y todavía no tiene responsable ni fecha objetivo. Estos dos campos son opcionales en el modelo actual: su ausencia es una tarea de organización, no corrupción de datos. No se determinó si su contenido es ficticio o real.

El bucket `expedientes` es privado, admite PDF, PNG y JPEG, tiene límite de 10 MiB por objeto y no contiene objetos en el corte revisado.

## Comprobaciones de acceso e integridad

Se ejecutaron transacciones `READ ONLY` con el rol PostgreSQL `authenticated` y el contexto de cada perfil existente. Se comparó la visibilidad real con el área autorizada calculada previamente. También se comprobó un contexto sin perfil municipal. No se usaron contraseñas ni se iniciaron sesiones de esos usuarios.

| Perfil comprobado | Expedientes esperados | Expedientes visibles | Solicitantes visibles | Eventos visibles |
|---|---:|---:|---:|---:|
| Administración | 1 | 1 | 1 | 1 |
| Mesa de Partes | 1 | 1 | 1 | 1 |
| Gestor de otra área | 0 | 0 | 0 | 0 |
| Consulta de otra área | 0 | 0 | 0 | 0 |
| Sin perfil municipal | 0 | 0 | 0 | 0 |

Las métricas devolvieron el mismo número de expedientes autorizado. El rol cliente no dispone de actualización directa de expedientes o perfiles ni de borrado del historial. Ninguna tabla propia permite lectura al rol `anon`. Las funciones de negocio públicas revisadas no conceden ejecución a `anon`; sus operaciones privilegiadas comprueban autorización en el servidor y fijan `search_path`.

Se verificaron resultados cero en estas comprobaciones:

- Solicitantes duplicados por tipo y número de documento.
- Expedientes sin evento inicial o cuyo último evento contradiga su estado o área actual.
- Responsables inválidos en expedientes pendientes.
- Personal o trámites activos vinculados con áreas inactivas.
- Expedientes sin archivar en áreas inactivas.
- Fichas de adjuntos sin objeto, u objetos sin ficha.
- Cuentas Auth sin perfil municipal e invitaciones vencidas sin utilizar.

Las comprobaciones de documentos y duplicados tienen una muestra mínima: no hay adjuntos y solo hay un solicitante. No sustituyen pruebas de escritura o carga. Se comparó además el cuerpo desplegado de nueve funciones relevantes con las migraciones del repositorio; los nueve coincidieron.

## Cambios recomendados

### 1. Corregir los datos de contacto del solicitante — prioridad alta

**Hallazgo confirmado por la función desplegada:** `private.register_case` inserta el solicitante con `ON CONFLICT (document_type, document_number) DO NOTHING`. Si ya existe con el mismo nombre, acepta el nuevo expediente, pero el correo y teléfono introducidos en ese nuevo registro no se guardan. La pantalla de detalle sigue mostrando el contacto anterior porque consulta el registro compartido de `applicants`.

Además, una diferencia de nombre bloquea el registro y remite al administrador, pero actualmente no existe una operación de aplicación para corregir solicitantes con autorización, control de versión e historial. Administración admite áreas, trámites y personal.

**Propuesta:** añadir una operación para corregir solicitantes con motivo obligatorio, permisos y control de versión; detectar y comunicar diferencias al registrar un nuevo expediente. Conservar en cada expediente una instantánea de la identidad y el contacto declarados en su recepción, separada de la ficha actual del solicitante. Así una corrección posterior no reescribe la información histórica.

**Verificación necesaria al implementar:** dos solicitudes del mismo documento con contactos diferentes, corrección de un nombre, rechazo de cambios por perfiles no autorizados, concurrencia y conservación de la constancia anterior. Este comportamiento se identificó por inspección; no se crearon solicitudes de prueba en la base alojada.

### 2. Verificar los adjuntos en el servidor — prioridad alta

**Hallazgo confirmado por permisos y funciones:** el cliente calcula la huella SHA-256 y envía `media_type`, `size_bytes` y `sha256`. La política de inserción comprueba acceso al expediente, existencia del objeto y propietario; las restricciones comprueban formato y rangos. No se contrasta en servidor que el tamaño, el tipo y la huella declarados correspondan a los bytes del objeto.

El cliente oficial sí valida la firma del archivo antes de subirlo y compara SHA-256 al descargar. El bucket privado, sus límites y el aislamiento por expediente están activos. Lo pendiente es que esa comprobación del contenido sea autoritativa también para llamadas directas a la API.

**Propuesta:** incorporar una finalización de carga en servidor que valide objeto, tamaño, tipo detectado y huella, y publique la ficha documental únicamente después de esa comprobación. Añadir estados de carga/verificación y una reconciliación de objetos cuya subida se completó pero cuya ficha falló. El análisis antimalware sería una protección adicional, distinta de verificar tipo y huella.

**Verificación necesaria al implementar:** metadatos que no coinciden con los bytes, extensión engañosa, intento fuera del área, cierre del expediente durante una carga y reintento tras un fallo. No se subieron archivos alterados a la base alojada durante esta revisión.

### 3. Confirmar y automatizar los respaldos — prioridad alta antes de operación

**Estado comprobado:** existe `scripts/municipal_backup.py`, documentación y un ensayo de restauración con datos ficticios en CI. El repositorio no configura una ejecución periódica; `docs/RESPALDOS.md` lo indica expresamente. No se consultó el historial de backups de la plataforma ni se puede afirmar que no existan copias realizadas por otro operador.

**Propuesta:** establecer frecuencia y retención según la pérdida de datos tolerable, guardar copias cifradas fuera del repositorio, registrar éxito o fallo y realizar restauraciones periódicas en un entorno separado. Incluir los bytes de Storage: una copia de PostgreSQL por sí sola no los conserva.

Referencia: [respaldos de Supabase](https://supabase.com/docs/guides/platform/backups).

### 4. Completar el catálogo y el modelo operativo — siguiente etapa funcional

**Estado comprobado:** solo existe `GENERAL`, una solicitud de referencia; no hay procedimientos marcados como oficiales. `municipal_settings.configured` sigue en `false` y el ubigeo está vacío. No hay tablas de versiones del TUPA, requisitos estructurados, calendario laboral, suspensiones de plazos o constancias de notificación.

**Propuesta:** empezar por los procedimientos públicos pertinentes al alcance elegido, con fuente, vigencia, versión y requisitos verificables. Añadir el ubigeo tras verificarlo. Mantener separados los objetivos internos de los plazos legales: estos últimos requieren reglas validadas de cómputo, feriados y suspensiones. La conformidad operativa no debe inferirse de haber completado campos.

Para crecer hacia otras áreas, conviene añadir jerarquía organizativa y relaciones de representantes de personas jurídicas cuando esos procesos se incorporen. No hace falta crear decenas de tablas sin un flujo concreto. Este es un piloto de expedientes, no la base completa de la municipalidad.

### 5. Planificar mantenimiento y endurecimiento de acceso

**Estado comprobado:** el servidor informa PostgreSQL **17.6**. El anuncio de Supabase del 25 de septiembre describe el despliegue de **17.11** con correcciones de seguridad. Preparar la actualización soportada por la plataforma, comprobar disponibilidad para este proyecto y verificar compatibilidad y recuperación antes de ejecutarla.

Las consultas de catálogo no encontraron índices `ltree`, índices GiST de flotantes ni operadores personalizados afectados por las incompatibilidades indicadas. Las funciones propias no usan cifrado PGP. Esto no certifica todos los objetos gestionados del proveedor ni cualquier consumidor externo de la base.

Referencia: [cambios de PostgreSQL 15.19 / 17.11](https://supabase.com/changelog/postgres-15-19-17-11-breaking-changes).

El asesor de seguridad también informa **protección contra contraseñas filtradas desactivada**. Evaluar su activación si el plan lo permite; la documentación consultada la limita a Pro o superior. Mantener identidades individuales para que el historial represente a la persona que realiza cada operación. No se cambiaron credenciales ni se contrataron servicios.

Referencia de remediación: [seguridad de contraseñas](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

## Alertas que no justifican cambios automáticos

- **RLS sin política en `private.staff_invitations`:** aviso informativo. La tabla tiene RLS y no concede lectura ni inserción directa al cliente; el acceso pasa por funciones administrativas autorizadas. No se debe añadir una política permisiva para silenciarlo. [Explicación del asesor](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy).
- **15 índices sin uso registrado:** aviso informativo con un volumen de un expediente. No demuestra que sobren: varios respaldan claves foráneas y filtros que se utilizarán al crecer. Conservarlos y revisar planes y estadísticas con una carga representativa. [Explicación del asesor](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index).
- **Rendimiento de búsqueda:** existen índices para claves y filtros principales. La búsqueda por fragmentos de asunto usa `ILIKE` en la bandeja y `strpos(lower(...))` en el reporte. Si el volumen lo exige, medir ambas consultas y decidir una estrategia de búsqueda coherente antes de crear índices adicionales; un índice de trigramas no acelera automáticamente cualquier expresión `strpos`.

## Alcance de la revisión

Se revisaron metadatos y recuentos de la base alojada, asesores de seguridad y rendimiento, restricciones, índices, permisos, políticas, disparadores, funciones y código que consume la base. No se hizo una prueba de carga, una restauración real, un ataque de escritura ni un inicio de sesión por navegador. No se verificaron políticas de red, configuración SMTP, configuración completa de Auth ni el historial de backups administrados.

El orden propuesto es: resolver datos de contacto y verificación documental; confirmar respaldos y mantenimiento; luego ampliar el catálogo y los flujos. Los resultados observados sustentan continuar sobre la estructura existente, sin rehacer la base desde cero.
