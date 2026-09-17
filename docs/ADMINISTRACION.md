# Administración de MuniGest

Entrar con una cuenta administradora y abrir **Administración** en el menú. La pantalla incluye búsqueda, páginas de 50 registros, registros inactivos y acceso al historial de cada ficha.

## Áreas

**Crear área** permite registrar código interno, nombre, tipo y enlace HTTPS de referencia. **Editar e historial** permite corregirlos, desactivar o reactivar el área. Cada guardado solicita un motivo.

La desactivación requiere que el área no tenga personal activo, trámites activos ni expedientes sin archivar. Primero se reasignan los perfiles y las fichas; los expedientes se derivan o concluyen y archivan mediante el flujo habitual. No se borran áreas ni referencias históricas.

Los códigos usan de 2 a 20 letras sin tildes, números, guion o guion bajo; se guardan en mayúsculas. Las áreas creadas como referencia no acreditan por sí mismas su incorporación al organigrama municipal.

## Trámites

**Crear trámite** registra una ficha del catálogo: código, nombre, área, requisitos, sustento y datos opcionales de importe y plazo. Marcar una ficha como contrastada con la fuente oficial exige registrar su sustento. Es una declaración del administrador que hizo la revisión; la aplicación no certifica automáticamente el contenido.

Un importe vacío significa **no registrado** y un importe `0` significa **gratuito según la ficha**. No deben confundirse. El plazo es un entero de 1 a 3650 días; puede dejarse vacío. La ficha todavía no distingue días hábiles y calendario: esta precisión debe quedar en el sustento y no se utiliza para calcular vencimientos.

Las fichas activas aparecen en **Áreas y trámites**, con su área, importe y plazo registrados. El catálogo orienta la atención; no aplica tarifas, no genera cobros, no calcula plazos legales y todavía no vincula una ficha específica a cada expediente. El registro de expedientes mantiene su selección explícita de área y fecha objetivo interna.

## Personal

Permite editar el nombre, rol, área y estado de perfiles existentes. Los roles **Gestor** y **Consulta** requieren un área. Activar un perfil con área asignada requiere que el área esté activa. Una cuenta desactivada deja de acceder a los datos en las siguientes operaciones; la información que ya descargó no se puede retirar de su dispositivo.

El administrador no puede desactivar su propia cuenta ni retirarse el rol Administrador desde este módulo. Puede editar otros administradores. Los cambios administrativos se serializan y comprueban nuevamente al actor dentro de la transacción, por lo que dos administradores no pueden dejarse mutuamente sin acceso mediante solicitudes simultáneas.

Esta pantalla no crea identidades de Auth, no cambia correos ni restablece contraseñas. El alta de cuentas individuales continúa mediante la [herramienta Python de alta](USUARIOS.md) o el procedimiento operativo allí documentado. Nunca se solicita una clave administrativa de Supabase en la aplicación.

## Historial y edición simultánea

Cada guardado desde Administración conserva actor, fecha, motivo y copia anterior y posterior del registro en `admin_events`. La pantalla muestra los últimos 25 cambios; las versiones completas permanecen en la base. Solo los administradores activos pueden consultar este historial. No hay operaciones de edición ni borrado de eventos desde la aplicación.

El historial comienza con el primer guardado desde este módulo. No reconstruye importaciones anteriores ni cambios realizados directamente por un operador de base de datos. El alta operativa de identidades sigue su propio procedimiento.

Si otra persona guardó primero, la versión obsoleta se rechaza. Volver a la lista, abrir el registro actual y volver a aplicar únicamente los cambios necesarios. Si se pierde la conexión durante un guardado, comprobar el historial antes de repetir: la operación podría haberse completado.

## Despliegue y verificación

La migración `municipal_administration` agrega versiones a los tres catálogos, historial protegido por RLS, dos RPC públicas con verificación de administrador y bloqueos que coordinan la desactivación de áreas con altas y derivaciones. Los clientes conservan prohibidas las escrituras directas de catálogos y perfiles.

Las pruebas de `tests/administration_contract.sql` se ejecutan exclusivamente en PostgreSQL local y terminan con rollback. La CI aplica todas las migraciones y los contratos de permisos sobre PostgreSQL 17. El modo demostración conserva sus cambios en memoria, separados de Supabase.
