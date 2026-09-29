# Integridad y operación de la base municipal

Implementación posterior a la [revisión del 29 de septiembre](REVISION_BD_2026-09-29.md). Proyecto: `lxvmwjcqdjoidgpinmgm`.

## Solicitantes

Administración incluye **Solicitantes**: búsqueda por nombre o documento, edición de nombre, documento, correo y teléfono, motivo obligatorio, control de versión e historial con actor, antes y después. Solo administradores activos pueden corregir las fichas. No se crean solicitantes aislados desde esta pantalla.

Cada expediente conserva su propia instantánea de los datos declarados en la recepción. Si la misma persona proporciona otro correo o teléfono en otra solicitud, esos contactos pertenecen a esa nueva solicitud. La corrección de la ficha actual no modifica constancias ni contactos de solicitudes anteriores. Si un documento ya tiene otro nombre registrado, se solicita una corrección autorizada antes de continuar.

Para expedientes previos a esta mejora se copia la ficha disponible al migrar y se marca `origin=migration_current_record`. No se inventa un historial de identidad o contacto anterior. La interfaz distingue esos datos de una captura realizada al recibir la solicitud.

## Documentos

Un disparador del servidor comprueba permiso, propietario del objeto, ruta, bytes iniciales, extensión, tipo, tamaño y SHA-256 antes de confirmar la ficha documental. Lee el objeto de Storage usando la sesión del operador, por HTTPS y con destino fijo al proyecto municipal. La extensión `http` no concede ejecución a los clientes. No se guardan tokens en tablas, archivos de configuración ni migraciones.

El transporte reenvía únicamente `Authorization` al endpoint autenticado de Storage. No depende de `apikey` en PostgreSQL: el gateway REST elimina ese encabezado. Se comprobó el acceso al endpoint real con la sesión del piloto y sin `apikey`, y la integridad binaria del transporte HTTP con una imagen pública conocida.

La lectura conserva los límites predeterminados de la extensión `http` 1.6 del proveedor (5 segundos por petición y 1 segundo de conexión) y pide como máximo 10 MiB más un byte mediante Range; también se aplica el límite de 10 MiB del bucket. Un fallo de lectura o una discrepancia cancela la ficha y su evento. La fecha `verified_at` identifica una verificación realizada por el servidor; los documentos antiguos no reciben una verificación ficticia.

`finalize_document` permite confirmar un mismo intento sin duplicar fichas ni eventos. Si el cliente pierde la respuesta, consulta si esa ficha se confirmó antes de mostrar un error. No se repite automáticamente una subida ni se elimina evidencia documental.

La firma inicial y la huella no son un análisis antimalware ni certifican la validez jurídica del documento. Para volúmenes mayores, separar la verificación en un servicio Python de procesamiento permitiría evitar la espera de red en PostgreSQL. Se mantiene el límite actual del piloto.

## Diagnóstico y catálogo

Administración muestra recuentos de fichas sin objeto, cargas sin registrar de más de una hora, documentos antiguos sin verificación, pendientes sin responsable y pendientes sin fecha objetivo. El diagnóstico no elimina ni reasigna datos automáticamente.

Las fichas de trámites admiten fuente HTTPS y fechas opcionales de vigencia. Marcar una ficha como oficial requiere sustento y fuente. Una ficha fuera de vigencia no se admite para una nueva clasificación; los expedientes anteriores conservan su instantánea. Los plazos del catálogo siguen siendo informativos: no se convierten en vencimientos legales sin reglas verificadas de cómputo.

El ubigeo de la sede se completa como `140101`, distrito de Chiclayo, con referencia en el [anexo 2 de SUNAT](https://www.sunat.gob.pe/legislacion/superin/2001/100.htm). No representa toda la provincia. La configuración operativa permanece pendiente de conformidad municipal; el catálogo no incorpora tarifas ni procedimientos inventados.

## Respaldos y mantenimiento

La herramienta de respaldos admite ejecución automática con credenciales del entorno, sin prompts y sin imprimir valores secretos. `.github/workflows/backup.yml` define una ejecución diaria a las 03:15 de Lima y retención de archivos cifrados de 30 días. El horario se activa únicamente cuando `MUNICIPAL_BACKUPS_ENABLED=true` y se han configurado sus tres secretos; también puede lanzarse manualmente. Ver [RESPALDOS.md](RESPALDOS.md).

**Preparar un workflow no acredita copias realizadas.** Debe comprobarse una ejecución y la recuperación antes de considerar el respaldo operativo. La activación depende de configurar las credenciales del operador; no están disponibles en el código ni se obtienen de las sesiones de los usuarios.

La actualización del motor administrado y la protección contra contraseñas filtradas se gestionan en el panel de Supabase. El proyecto usa el plan gratuito; no se contratan funciones de pago. Las migraciones de aplicación no actualizan el binario PostgreSQL del proveedor.

## Validación

- Pruebas Python: conservación de contactos, corrección autorizada, versiones, instantáneas, respuesta de carga perdida y rechazo temprano de respaldos sin credenciales.
- Contratos PostgreSQL: mismos roles y reglas de negocio, más correcciones históricas, rechazo de metadatos falsos, archivos binarios con bytes NUL, credenciales ausentes, Storage no disponible e idempotencia documental.
- El transporte HTTP de los contratos usa un doble exclusivo de la base de pruebas. No se desactivan los controles de permisos o contenido del código de producción.
- CI instala `postgresql-17-http`, ejecuta las migraciones completas y ensaya la restauración. El entorno de restauración requiere esa extensión además de PostgreSQL 17.
- La prueba de navegador usa datos ficticios para verificar la edición de solicitantes y la presentación de su historial, junto con los flujos anteriores de sesión, adjuntos y exportaciones.
