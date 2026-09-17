# Modelo de acceso

| Perfil | Lectura | Escritura |
|---|---|---|
| Administrador | Expedientes municipales e historial de Administración | Registro, actuaciones y gestión de catálogos y perfiles existentes |
| Mesa de Partes | Expedientes municipales | Registro y actuaciones |
| Gestor | Expedientes del área actual | Actuaciones y adjuntos de su área |
| Consulta | Expedientes del área actual | Ninguna |
| Sin perfil activo / anónimo | Ningún expediente | Ninguna |

La cuenta y el rol se consultan desde `staff_profiles`; no proceden de metadatos editables del usuario. Los clientes no tienen permisos para insertar o modificar perfiles, tablas maestras, expedientes o eventos directamente. Las operaciones de registro y actuación son transaccionales, autorizan al actor en servidor y generan el historial.

Las funciones con privilegios elevados se mantienen en `private`, con `search_path` fijo y comprobación de `auth.uid()`. Los wrappers de la API son `SECURITY INVOKER` y no están habilitados para `anon`. Todas las tablas de aplicación tienen RLS. El contador anual es una tabla privada sin permisos de cliente y con una política de denegación explícita. Solo las operaciones internas autorizadas del registro lo incrementan.

Administración usa operaciones transaccionales que consultan el perfil activo en la base, comparan la versión del registro y escriben `admin_events` en la misma transacción. Un bloqueo serializa los cambios administrativos y la autorización se consulta después de adquirirlo. Se impide la desactivación o retirada del rol del propio administrador. Las comprobaciones de área activa adquieren un bloqueo compartido que se coordina con la desactivación del área; esta última rechaza personal, fichas activas o expedientes sin archivar. No se permite borrar ni modificar el historial desde la API.

Los archivos se guardan en un bucket privado. El acceso depende del expediente. Los objetos y su metadata no se borran ni reemplazan desde la aplicación. Si la subida termina pero falla el registro de la metadata, se informa al operador; un administrador debe reconciliar los objetos sin ficha. La validación de tipo/tamaño y la huella SHA-256 no sustituyen un servicio de análisis antimalware.

Las sesiones se mantienen en memoria. No hay registro abierto en la interfaz. Los permisos se comprueban con cada operación; desactivar un perfil bloquea el acceso a datos sin esperar a que caduque el JWT. La renovación de sesión está serializada por usuario. No se comparten clientes Supabase globales entre usuarios del servidor web.

El historial guarda actor, fecha y motivo. No contiene copias de contraseñas ni JWT. El CSV omite documentos de identidad y contactos, y neutraliza prefijos de fórmula; exporta solamente la página visible.

Las pruebas automatizadas cubren aislamiento por área, perfil de consulta, usuario inactivo, acceso anónimo, bloqueo de edición directa, prohibición de borrado de auditoría, concurrencia e idempotencia. Falta la validación operativa con cuentas reales y la revisión integral del despliegue de producción; no se declara el sistema certificado ni listo para uso oficial sin esa validación.
