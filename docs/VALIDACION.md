# Validación de la versión 0.1

Fecha: 16 de septiembre de 2026.
Última actualización: 23 de septiembre de 2026.

## Resultados comprobados

| Comprobación | Resultado |
|---|---|
| Pruebas Python | 116 aprobadas, incluidos reportes, cuentas, respaldos y arranque desde Python compilado sin los archivos originales |
| Análisis estático Ruff | Sin errores |
| Construcción de las pantallas | Login, resumen, bandeja, registro, detalle, catálogo y Administración (listas y formularios); anchos 390 y 1280 |
| Composición de filas y columnas | Ningún hijo expandido dentro de un contenedor con `wrap=True` en las pantallas comprobadas |
| Arranque del servidor Flet | HTTP 200 usando PORT; configuración inválida rechazada antes del arranque |
| Herramienta Python de alta | API simulada: cuatro roles, aislamiento de proyecto, correos confirmados, reanudación, permisos existentes y fallos parciales |
| Cuentas del piloto en Supabase real | Cuatro creadas mediante Auth Admin; inicio de sesión, perfil activo, rol y área comprobados para cada una |
| Restricción de edición de perfiles | La cuenta de consulta recibió HTTP 403 al intentar una actualización directa |
| Cierre de la función temporal de alta | HTTP 410 con sesión autenticada tras sustituirla por una respuesta de operación cerrada |
| Esquema SQL en PostgreSQL aislado (PGlite) | Las seis migraciones aplicadas correctamente, incluidos reportes con RLS |
| Contrato SQL | Roles, aislamiento por área, idempotencia, control de versión, estados, bloqueo de edición directa, adjuntos y auditoría aprobados |
| Contrato SQL de Administración | Roles, historial, versiones obsoletas, protección de cuenta propia, áreas en uso y validación de fichas aprobados |
| Contrato SQL de organización | Trámite histórico, asignación válida, liberación al derivar, bloqueo de perfiles con pendientes, permisos y versiones obsoletas aprobados |
| Contrato SQL de reportes | Consulta completa de 1501 filas, límite exacto de 10000, rechazo de 10001, filtros, fechas de Chiclayo, permisos y documento de identidad parcial |
| Documentos PDF | Constancia de una página, descripción de varias páginas, resumen con datos y vacío; renderizados y revisados visualmente |
| Migraciones en Supabase municipal | `20260916153745_municipal_core`, `20260916154951_municipal_access_hardening`, `20260916162200_chiclayo_institutional_configuration`, `20260917210945_municipal_administration`, `20260917214043_municipal_work_queue` y `20260918184510_municipal_reports` |
| Configuración de Chiclayo | Nombre MPCH, 14 gerencias y un punto de recepción activos; referencia AC inactiva; fuentes oficiales registradas |
| Consultas anónimas a la API real | `cases` y `staff_profiles` rechazadas con HTTP 401 |
| Asesor de seguridad de Supabase | Sin avisos de tablas o RLS; un aviso Auth por protección contra contraseñas filtradas desactivada |
| Asesor de rendimiento | 14 índices todavía sin uso; información esperable en tablas nuevas sin datos operativos |

Los índices soportan filtros, relaciones y ordenaciones del flujo; no se eliminaron por falta de uso en una base nueva. [Explicación del aviso](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index).

El proyecto municipal tiene nueve tablas públicas protegidas por RLS, un contador interno en `private` y un bucket documental privado. El estado final comprobado tiene quince destinos activos, cuatro perfiles de prueba y cero expedientes. El catálogo conserva una solicitud general de referencia y ningún trámite marcado como oficial. `configured=false` indica que aún falta conformidad operativa de la MPCH. No se cargaron personas ni expedientes reales. No se modificó EcoSphere.

La adaptación de identidad, catálogo y demostración pasó nuevamente las 31 pruebas Python y Ruff. El contrato SQL también pasó después de aplicar las tres migraciones en una base aislada. Las pruebas de arranque HTTP y rechazo anónimo corresponden a la validación inicial; esta adaptación no modifica servidor, autenticación ni políticas RLS.

La entrega posterior de alta de usuarios y archivos de despliegue pasó 45 pruebas Python y Ruff. Se volvió a comprobar el arranque HTTP con `PORT` y el rechazo de configuración inválida. Las llamadas de la herramienta Python se probaron con `httpx.MockTransport`.

Después se crearon cuatro identidades ficticias del piloto mediante una función temporal y la API Auth Admin del proyecto municipal. Se comprobó el acceso real de administrador (GTIE), mesa de partes (MP), gestor (GDU) y consulta (GDU), y se cerraron las sesiones de validación. La función rechazó una petición sin autorización y, una vez cerrada, devolvió HTTP 410 incluso con autenticación. El cliente de consulta recibió HTTP 403 al intentar modificar un perfil. Las credenciales se entregaron fuera de Git. No se configuró una clave administrativa en la aplicación.

El asesor de seguridad actual informa `auth_leaked_password_protection`: la protección contra contraseñas filtradas está desactivada. La organización usa el plan Free y esta función requiere Pro o superior, según la [documentación de seguridad de contraseñas](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection). No se cambió el plan. Las cuentas del piloto se crearon con contraseñas aleatorias independientes y deben retirarse antes del uso con información real.

El 17 de septiembre se actualizó la contraseña de la cuenta administradora a petición del responsable del piloto, mediante la API Auth con una sesión de esa misma cuenta. Se verificó un nuevo inicio de sesión real con el alias `admin`, conservando el mismo usuario Auth y perfil administrador activo. La contraseña vigente se conserva fuera del repositorio. Las pruebas del alias verifican el envío a Auth, la exigencia de un perfil activo, el rol devuelto por el servidor, el acceso por correo y su limitación al proyecto municipal.

## Validación de Administración

El módulo Administración pasó 62 pruebas Python y ambos contratos SQL con las cuatro migraciones en PGlite. Se comprobó el recorrido del formulario para crear un área, guardarla y editarla nuevamente usando la versión confirmada. Se construyeron las listas y los formularios de áreas, trámites y personal a anchos 390 y 1280. Estas comprobaciones todavía no sustituyen la revisión visual en Windows.

La migración de Administración se aplicó al proyecto municipal y se comprobó con sesiones Auth reales: el administrador leyó 16 áreas y cuatro perfiles, guardó la ficha GENERAL conservando su contenido y verificó las versiones anterior y posterior en el historial. La petición anónima al listado recibió HTTP 401. Mesa de partes, gestor y consulta recibieron rechazo tanto al listar como al intentar guardar, y no pudieron leer eventos administrativos. Todas las sesiones de verificación se cerraron. El estado comprobado conserva cero solicitantes y cero expedientes, con un evento administrativo de revisión de la ficha GENERAL.

Después de esta migración, los asesores de Supabase no detectaron nuevos avisos de seguridad. Permanecen el aviso Auth sobre protección de contraseñas filtradas y los avisos informativos de índices sin uso, enlazados arriba. Las pruebas de versiones obsoletas no equivalen a una prueba de carga con múltiples operadores simultáneos.

## Validación de trámites, responsables y bandeja

La ampliación pasó 80 pruebas Python, Ruff y tres contratos SQL con las cinco migraciones en PGlite. El nuevo contrato comprueba conservación de fichas, rechazo de responsables inactivos o de otra área, idempotencia del registro, liberación al derivar, permisos de organización, historial anterior/posterior y protección de perfiles con pendientes. También se comprobaron los límites de días completos en horario de Chiclayo y las fechas objetivo de hoy, vencidas y próximas.

La prueba de interfaz recorrió registro con trámite y responsable, cambio de prioridad y objetivo, derivación y accesos rápidos a anchos 390 y 1280. El CSV incluye trámite y responsable y conserva la exclusión de documentos de identidad. La prueba construye controles y ejecuta sus manejadores; no certifica el dibujo nativo en dispositivos.

En Supabase se aplicó `20260917214043_municipal_work_queue`. Las cuatro cuentas del piloto pudieron consultar el directorio y la bandeja con los nuevos filtros y la relación explícita de responsable. Las mutaciones de un expediente inexistente fueron rechazadas; Consulta no obtuvo permiso de organización y la petición anónima recibió HTTP 401. Las sesiones se cerraron al terminar. La base conserva cero expedientes y cero solicitantes: las escrituras completas de este flujo se comprobaron exclusivamente en bases aisladas y en la demostración, sin insertar solicitudes ficticias en Supabase.

Los asesores no reportaron nuevos avisos de seguridad; permanecen el aviso Auth y los índices todavía sin uso documentados arriba. La RLS conserva el alcance por área. Faltan las pruebas de carga concurrente y el uso integral desde dispositivos reales.

## Validación de constancias y reportes

El 18 de septiembre se añadieron constancias PDF y reportes de todos los resultados filtrados. Pasaron 90 pruebas Python, Ruff y los cuatro contratos SQL con las seis migraciones en PGlite. El contrato nuevo comprueba que las descargas son funciones `STABLE` con `SECURITY INVOKER`, sin acceso anónimo, y verifica todos los roles, perfiles inactivos, filtros combinados y límites de días en Chiclayo.

Se comprobaron 1501 expedientes sin truncar, una consulta de exactamente 10000 y el rechazo explícito de 10001 resultados. Los datos ficticios se crearon exclusivamente en la base local y se revirtieron. El resumen utiliza el día del corte entregado por el servidor; las fechas objetivo de expedientes atendidos o archivados no se cuentan como pendientes vencidos.

Las pruebas Python exportan 1205 filas únicas, protegen fórmulas CSV, comprueban caracteres en español y texto literal con etiquetas, y verifican que los archivos omiten documentos de identidad completos y contactos. La interfaz de reportes y los manejadores de descarga se probaron a anchos 390 y 1280, incluida la actualización de datos antes de descargar y el rechazo después de inactivar un perfil de demostración.

Los PDF se generaron con ReportLab, se renderizaron con Poppler y se revisaron: constancia corta, descripción larga distribuida en varias páginas, reporte con resultados y reporte vacío. Se corrigió un salto de página que dejaba demasiado espacio antes de una descripción extensa. Esto valida el contenido de los archivos, no el selector nativo de archivos de Windows o Android.

Se aplicó `20260918184510_municipal_reports` al proyecto municipal. El asesor no detectó nuevos problemas de seguridad; conserva el aviso de protección de contraseñas y 14 índices sin uso, con las referencias de remediación enlazadas arriba.

Las cuatro cuentas reales del piloto consultaron el reporte general, Mis pendientes y un intervalo de ingreso. Cada respuesta vacía generó correctamente el CSV y el PDF; una constancia para un identificador inexistente fue rechazada. Ambas funciones rechazaron llamadas anónimas con HTTP 401. Las sesiones de comprobación se cerraron con alcance local. La base conserva cero solicitantes y cero expedientes: las constancias con contenido y los reportes con volumen se verificaron en pruebas aisladas.

## Validación de cuentas y respaldos

El 23 de septiembre pasaron 113 pruebas Python, Ruff y cinco contratos SQL sobre las siete migraciones en PGlite. Las pruebas cubren invitaciones de un solo uso, caducidad, revocación, administrador inactivo, rechazo de escalada por metadata, auditoría y permisos. Recuperación y confirmación se probaron con respuestas Auth simuladas, incluidos errores y cierre de sesiones temporales. Se construyeron las nuevas pantallas a anchos 390 y 1280.

Se aplicó la migración de cuentas al proyecto municipal. Con las sesiones reales del piloto, solo Administrador pudo listar invitaciones; Mesa de partes, Gestor y Consulta fueron rechazados. Se cerraron esas sesiones con alcance local. No se crearon usuarios reales adicionales ni se enviaron correos externos. La configuración SMTP y la entrega real a un buzón siguen sin verificarse.

El respaldo cifrado del 23/09/2026 conserva 31 filas en 13 tablas: incluye cuatro identidades Auth, cuatro cuentas y sus cuatro perfiles; 16 áreas, una ficha de trámite, un evento administrativo y la configuración institucional. La base conserva cero expedientes, solicitantes, invitaciones y adjuntos. Las filas se restauraron y compararon mediante sus tipos PostgreSQL en una base PGlite aislada; un segundo intento sobre el destino ocupado fue rechazado.

Por separado, se verificó una copia cifrada con un expediente ficticio, su solicitante, dos eventos y un adjunto: se restauraron las filas y los bytes del archivo. Esos datos solo existen en el entorno local. También se probaron contraseña de respaldo incorrecta, archivo alterado, adjunto ausente, proyecto equivocado y rutas inseguras. El workflow incorpora el mismo ensayo de respaldo en dos bases PostgreSQL 17 separadas.

Estos ensayos comprueban datos y documentos; no equivalen a recuperar los servicios Auth/Storage en otro proyecto alojado. La herramienta limita el ensayo a una base local vacía y no ofrece sobrescritura de producción. Ver [alcance y uso del respaldo](RESPALDOS.md).

El asesor de seguridad mantiene el aviso conocido de protección contra contraseñas filtradas. Añade un aviso informativo por RLS sin políticas en `private.staff_invitations`: es intencional, pues ningún cliente puede leer esa tabla directamente; solo las funciones con autorización de administrador acceden a ella. Los índices nuevos todavía no tienen uso operativo. No se cambió el plan ni la contraseña del piloto.

## Validación del APK Android

El 23 de septiembre se generaron APK universales con Flet 1.0.0 y Python 3.13,
para ARM64, ARM de 32 bits y x86_64. La configuración declara Android 7 como
versión mínima. Se inspeccionó el archivo municipal: incluye únicamente la
configuración pública de `lxvmwjcqdjoidgpinmgm`, sin `.env`, contraseñas ni
herramientas administrativas; la fuente Vera del PDF se extrae como archivo.

La demostración pasó el recorrido automatizado en un emulador Android 15 x86_64:
instalación, apertura, resumen, menú, catálogo, expediente, generación y guardado
de la constancia PDF, adjunto mediante el selector nativo y cierre de sesión.
El PDF se recuperó del emulador y se comprobó su contenido con pypdf. Se revisaron
las capturas del resumen, catálogo, cabecera del expediente y documento adjunto.
El recorrido terminó sin excepciones Python ni desbordamientos de Flutter en
logcat. Los datos y el adjunto de esta prueba solo existen en la demostración.

La prueba real del APK detectó y permitió corregir dos fallos: la búsqueda
automática de `.env` fallaba cuando solo quedaban archivos `.pyc`, y la apertura
de un expediente conservaba el desplazamiento de la bandeja. El primero tiene
una regresión Python con el archivo original eliminado; el segundo se comprueba
abriendo el expediente desde una bandeja desplazada y localizando su cabecera.
También se serializaron las descargas de dependencias nativas para evitar
escrituras simultáneas en los metadatos ETag de Gradle.

La prueba de acceso reconoce los campos por su tipo nativo y verifica que la
contraseña esté protegida. UIAutomator no devuelve las etiquetas flotantes de
los campos Flutter en su árbol XML, aunque sí aparecen en la captura.

El cliente municipal también aprobó instalación, apertura, conexión TLS/Auth
con rechazo de credenciales vacías, recuperación e invitación y regreso al
inicio. Se revisaron las capturas de acceso e invitación. No se usaron cuentas
privadas, no se enviaron correos y no se escribieron expedientes en Supabase.
La autenticación con una cuenta válida no formó parte de esta prueba Android.

Ambas variantes y la publicación terminaron correctamente en la
[ejecución Android 4](https://github.com/VillenetMK/sistema-municipal/actions/runs/35880312397),
correspondiente al commit `249770b08c0d854f172dbfef007d305f9784235e`.
El [APK publicado](https://github.com/VillenetMK/sistema-municipal/releases/tag/android-piloto-4)
ocupa 66 930 485 bytes; su SHA-256 se comprobó tanto contra `SHA256SUMS.txt` como
contra el archivo publicado en GitHub. Las 116 pruebas Python, Ruff y los
contratos de PostgreSQL 17 aprobaron en la
[ejecución de comprobaciones](https://github.com/VillenetMK/sistema-municipal/actions/runs/35880312364).

El cliente municipal usa firma de pruebas y requiere Internet. Falta la prueba
en un teléfono físico con una cuenta válida, incluidos permisos del área,
operaciones con expedientes autorizados, rotación y pérdida de conexión. No se
certifica distribución en Google Play ni uso oficial municipal. Ver
[instalación, firma y alcance de las pruebas](ANDROID.md).

## Límites de esta validación

El 17 de septiembre se corrigió el panel vacío después del acceso: los encabezados, las tarjetas, la búsqueda y el historial mezclaban `wrap=True` con hijos `expand=True`. En Flet 1.0.0, [Row usa Wrap al activar el salto de línea](https://github.com/flet-dev/flet/blob/v1.0.0/packages/flet/lib/src/controls/row.dart) y [el control expandido requiere un padre Flex](https://github.com/flet-dev/flet/blob/v1.0.0/packages/flet/lib/src/controls/base_controls.dart). Se eliminaron las combinaciones incompatibles conservando el ajuste del texto. La prueba de regresión falló antes del cambio con ambos conjuntos de datos y pasó después; también pasaron las 46 pruebas Python y Ruff. El navegador de revisión bloqueó la dirección local, por lo que queda pendiente confirmar visualmente esta corrección en Windows.

La comprobación de pantallas construye controles con la versión instalada de Flet; no equivale a una revisión visual de píxeles. El navegador de revisión no pudo abrir la dirección local de este entorno. Se verificaron por separado el arranque HTTP y la construcción de los controles.

Las políticas se probaron en un PostgreSQL aislado con esquemas Auth y Storage mínimos; la API real se comprobó como cliente anónimo y con las cuatro cuentas del piloto. Las comprobaciones autenticadas cubren acceso, perfiles, lectura sin expedientes y rechazo de edición de perfiles; no equivalen a un recorrido completo con documentación municipal. Faltan pruebas integrales con usuarios municipales reales, cargas y descargas desde dispositivos reales, accesibilidad con lectores de pantalla, concurrencia bajo carga y recuperación integral en un proyecto Supabase de reemplazo.

Se compilaron y probaron APK en el emulador Android descrito arriba. No se compilaron instaladores Windows/Linux ni paquetes iOS/macOS. No se publicó la aplicación web. Las capacidades de despliegue y empaquetado no están certificadas para todos los destinos.

Dockerfile y Compose están preparados; su construcción no se ejecutó porque el entorno no dispone de Docker. La comprobación HTTP corresponde al proceso Python, no a una imagen construida.

El historial de pruebas SQL se ejecuta dentro de una transacción con rollback. Los scripts de bootstrap son únicamente para bases locales de pruebas. El workflow del repositorio repetirá las comprobaciones en PostgreSQL 17.
