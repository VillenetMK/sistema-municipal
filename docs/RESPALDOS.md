# Respaldo y ensayo de restauración

`scripts/municipal_backup.py` crea una copia cifrada del piloto y comprueba su integridad. La ejecuta el operador de base de datos; no forma parte del cliente Flet. El proyecto de origen está fijado a `lxvmwjcqdjoidgpinmgm` y se verifica la identidad de Chiclayo.

## Qué incluye

- Las nueve tablas públicas municipales, contadores e invitaciones privadas.
- Identidades y cuentas de acceso por correo, incluidos sus hashes de contraseña. Por eso la copia siempre se cifra.
- Las siete migraciones del repositorio y los objetos del bucket privado `expedientes`, incluidos objetos sin registro documental. Cada adjunto registrado se coteja con su tamaño y SHA-256.
- Inventario, conteos, fecha del corte y comprobaciones SHA-256. Cifrado AES-256-GCM y derivación de clave con scrypt.

La lectura de las tablas ocurre en una sola sentencia SQL. Los archivos del corte se descargan después; si un adjunto falta o cambia, el proceso falla y no entrega una copia completa aparente. La aplicación no permite sobrescribir documentos. Una carga posterior al corte pertenece al siguiente respaldo.

Es un respaldo lógico del piloto, con límite de 512 MiB en memoria. Rechaza esquemas desconocidos, MFA, usuarios por teléfono y proveedores externos para evitar omitir información necesaria. En esos escenarios debe utilizarse el procedimiento completo de Supabase, ampliado con copia de Storage.

No incluye sesiones activas, configuración SMTP, claves API/JWT, configuración de plataforma, DNS ni funciones Edge. No es una imagen física del servidor. Esos servicios se configuran por separado al recuperar un proyecto alojado.

## Crear y verificar una copia (PowerShell o terminal)

Desde la raíz del repositorio:

```powershell
uv sync --frozen --group operations
uv run --group operations python scripts/municipal_backup.py backup --output artifacts/Respaldo_municipal.mgb
uv run --group operations python scripts/municipal_backup.py verify artifacts/Respaldo_municipal.mgb
```

El primer comando de respaldo pide una frase privada, su repetición y un token personal del operador de Supabase. Si existen archivos, pide además una clave administrativa del proyecto para descargarlos. Los valores se introducen de forma oculta; no se pasan como argumentos ni se escriben en `.env`, en el código o en GitHub. Guardar la frase separada de la copia. El archivo de salida nunca sobrescribe otro existente.

La herramienta usa la API de administración solo para leer la fotografía de la base; las descargas usan la API de Storage. No escribe en el proyecto municipal. El límite del plan o de la API puede impedir copias grandes: en ese caso se informa fallo, no éxito parcial.

## Ensayar una restauración sin tocar el proyecto

Requiere PostgreSQL 17 y `psql` en el PATH. Crear una base local vacía, en una instalación destinada a pruebas:

```powershell
createdb -h 127.0.0.1 -U postgres munigest_restore
uv run --group operations python scripts/municipal_backup.py restore-test artifacts/Respaldo_municipal.mgb --output-dir artifacts/ensayo-restauracion
```

El destino está limitado a `127.0.0.1` y a la base `munigest_restore`; el SQL vuelve a comprobar el nombre y rechaza tablas preexistentes. No acepta una URL de Supabase. Se requieren privilegios locales para crear los roles de prueba y desactivar temporalmente los triggers de usuario durante la carga. Los triggers se reactivan; las restricciones y claves foráneas se conservan. La importación y comparación de todas las tablas ocurre dentro de una transacción. Las secuencias se ajustan al historial recuperado.

El ensayo recrea las tablas Auth mínimas necesarias para verificar sus datos; no inicia los servidores Auth ni Storage. Los documentos se reconstruyen bajo la carpeta del ensayo y se cotejan con sus huellas. `Restauracion_verificada.json` confirma el resultado. Si falla la escritura de archivos después de confirmar la base local, el comando informa operación incompleta; usar otro entorno vacío para repetir.

Conservar el informe, comprobar conteos y revisar los documentos. El ensayo rechaza una segunda carga sobre la misma base. Usar una instalación desechable para los siguientes ejercicios; no eliminar una base compartida solo para repetir una prueba.

## Recuperar un proyecto alojado

El ensayo anterior no sobrescribe producción. Para una recuperación real, preparar un proyecto Supabase de reemplazo, configurar sus servicios, aplicar las migraciones de la revisión del respaldo y seguir la guía oficial de restauración. Un operador debe adaptar la importación Auth a su esquema gestionado (incluidas columnas generadas), restaurar los objetos por la API de Storage, comprobar RLS con los cuatro roles y validar el acceso antes de cambiar la configuración de los clientes. El script no automatiza esa migración a un proyecto alojado.

Programar copias según el uso real y conservar varias generaciones fuera del repositorio, con acceso limitado al responsable. Hacer un nuevo ensayo después de cambiar esquema o almacenamiento. Esta entrega no configura una tarea programada ni contrata backups de pago.

Referencias: [respaldos de Supabase](https://supabase.com/docs/guides/platform/backups), [restauración de plataforma](https://supabase.com/docs/guides/self-hosting/restore-from-platform). Las copias de base de datos por sí solas no conservan los bytes de Storage.
