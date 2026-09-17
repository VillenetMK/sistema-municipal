# Validación de la versión 0.1

Fecha: 16 de septiembre de 2026.
Última actualización: 17 de septiembre de 2026.

## Resultados comprobados

| Comprobación | Resultado |
|---|---|
| Pruebas Python | 62 aprobadas, incluidas Administración, variantes de interfaz con y sin expedientes y acceso mediante alias |
| Análisis estático Ruff | Sin errores |
| Construcción de las pantallas | Login, resumen, bandeja, registro, detalle, catálogo y Administración (listas y formularios); anchos 390 y 1280 |
| Composición de filas y columnas | Ningún hijo expandido dentro de un contenedor con `wrap=True` en las pantallas comprobadas |
| Arranque del servidor Flet | HTTP 200 usando PORT; configuración inválida rechazada antes del arranque |
| Herramienta Python de alta | API simulada: cuatro roles, aislamiento de proyecto, correos confirmados, reanudación, permisos existentes y fallos parciales |
| Cuentas del piloto en Supabase real | Cuatro creadas mediante Auth Admin; inicio de sesión, perfil activo, rol y área comprobados para cada una |
| Restricción de edición de perfiles | La cuenta de consulta recibió HTTP 403 al intentar una actualización directa |
| Cierre de la función temporal de alta | HTTP 410 con sesión autenticada tras sustituirla por una respuesta de operación cerrada |
| Esquema SQL en PostgreSQL aislado (PGlite) | Las cuatro migraciones aplicadas correctamente, incluidas Chiclayo y Administración |
| Contrato SQL | Roles, aislamiento por área, idempotencia, control de versión, estados, bloqueo de edición directa, adjuntos y auditoría aprobados |
| Contrato SQL de Administración | Roles, historial, versiones obsoletas, protección de cuenta propia, áreas en uso y validación de fichas aprobados |
| Migraciones en Supabase municipal | `20260916153745_municipal_core`, `20260916154951_municipal_access_hardening`, `20260916162200_chiclayo_institutional_configuration` y `20260917210945_municipal_administration` |
| Configuración de Chiclayo | Nombre MPCH, 14 gerencias y un punto de recepción activos; referencia AC inactiva; fuentes oficiales registradas |
| Consultas anónimas a la API real | `cases` y `staff_profiles` rechazadas con HTTP 401 |
| Asesor de seguridad de Supabase | Sin avisos de tablas o RLS; un aviso Auth por protección contra contraseñas filtradas desactivada |
| Asesor de rendimiento | 15 índices todavía sin uso; información esperable en tablas nuevas sin datos operativos |

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

## Límites de esta validación

El 17 de septiembre se corrigió el panel vacío después del acceso: los encabezados, las tarjetas, la búsqueda y el historial mezclaban `wrap=True` con hijos `expand=True`. En Flet 1.0.0, [Row usa Wrap al activar el salto de línea](https://github.com/flet-dev/flet/blob/v1.0.0/packages/flet/lib/src/controls/row.dart) y [el control expandido requiere un padre Flex](https://github.com/flet-dev/flet/blob/v1.0.0/packages/flet/lib/src/controls/base_controls.dart). Se eliminaron las combinaciones incompatibles conservando el ajuste del texto. La prueba de regresión falló antes del cambio con ambos conjuntos de datos y pasó después; también pasaron las 46 pruebas Python y Ruff. El navegador de revisión bloqueó la dirección local, por lo que queda pendiente confirmar visualmente esta corrección en Windows.

La comprobación de pantallas construye controles con la versión instalada de Flet; no equivale a una revisión visual de píxeles. El navegador de revisión no pudo abrir la dirección local de este entorno. Se verificaron por separado el arranque HTTP y la construcción de los controles.

Las políticas se probaron en un PostgreSQL aislado con esquemas Auth y Storage mínimos; la API real se comprobó como cliente anónimo y con las cuatro cuentas del piloto. Las comprobaciones autenticadas cubren acceso, perfiles, lectura sin expedientes y rechazo de edición de perfiles; no equivalen a un recorrido completo con documentación municipal. Faltan pruebas integrales con usuarios municipales reales, cargas y descargas desde dispositivos reales, accesibilidad con lectores de pantalla, concurrencia bajo carga y restauración de respaldos.

No se compilaron APK, instaladores Windows/Linux ni paquetes iOS/macOS. No se publicó la aplicación web. Las capacidades de despliegue y empaquetado están documentadas, no certificadas para todos los destinos.

Dockerfile y Compose están preparados; su construcción no se ejecutó porque el entorno no dispone de Docker. La comprobación HTTP corresponde al proceso Python, no a una imagen construida.

El historial de pruebas SQL se ejecuta dentro de una transacción con rollback. Los scripts de bootstrap son únicamente para bases locales de pruebas. El workflow del repositorio repetirá las comprobaciones en PostgreSQL 17.
