# Alta de usuarios del piloto

El alta utiliza las cuatro funciones ya implementadas. Cada trabajador recibe una cuenta individual; las credenciales se asignan a una persona identificada.

| Rol | Acceso en MuniGest | Área inicial sugerida para la prueba |
|---|---|---|
| `admin` | Todos los expedientes y operaciones del piloto | GTIE |
| `mesa_partes` | Recepción, consulta global, derivación y actuaciones | MP |
| `gestor` | Expedientes asignados a su área y actuaciones permitidas | Área real del trabajador |
| `consulta` | Lectura de expedientes de su área | Área real del trabajador |

El rol `admin` de la aplicación no da acceso al panel de Supabase ni a su clave administrativa. La creación de identidades se realiza con la herramienta operativa descrita aquí o desde Supabase Auth. Las áreas sugeridas no designan a ningún funcionario real.

## Datos necesarios

Para cada persona: nombre completo, correo real, rol y código de área. El catálogo de áreas está en [CHICLAYO.md](CHICLAYO.md). En el estado verificado de esta entrega no hay cuentas Auth ni perfiles de personal: todavía no se proporcionaron identidades reales.

## Opción desde el panel de Supabase

1. Abrir [Authentication / Users del proyecto municipal](https://supabase.com/dashboard/project/lxvmwjcqdjoidgpinmgm/auth/users).
2. Crear la cuenta con su correo real y contraseña individual, siguiendo el mecanismo de verificación acordado con la persona.
3. Una vez confirmado el correo, asignar el perfil mediante la herramienta siguiente con `--user-id`, o mediante el bloque SQL de [puesta en marcha](PUESTA_EN_MARCHA.md).

La conexión utilizada durante el desarrollo permite consultar la base y asignar perfiles a identidades existentes. No expone una operación para crear cuentas Auth. No se insertan identidades directamente en las tablas internas de autenticación.

## Herramienta Python de alta

`scripts/provision_staff.py` se ejecuta en la terminal del operador que administra Supabase. No se distribuye dentro de la aplicación Flet ni del contenedor del servidor web.

Preparar un alta, sin conexión ni cambios:

```bash
uv run python scripts/provision_staff.py --email persona@example.com --name "Nombre completo" --role admin --department GTIE
```

Para ejecutarla, sustituir el correo y nombre de ejemplo por los datos reales y añadir `--apply --verified-email`. El segundo indicador significa que el operador **ya comprobó la titularidad del correo**: esta modalidad crea una cuenta con correo confirmado, sin enviar mensajes. No verifica la identidad automáticamente.

La herramienta solicita la clave `sb_secret_...` en un campo oculto de terminal y después la contraseña individual, dos veces. Alternativamente puede obtener la clave desde `SUPABASE_SECRET_KEY` suministrada por el gestor de secretos del operador. No poner esta clave en el `.env` de la aplicación, en el código, en el chat ni en los argumentos del comando.

Se comprueban proyecto, institución y área activa antes de crear la identidad. Después se guarda y vuelve a leer su perfil. Un perfil existente con permisos diferentes produce un error y conserva sus permisos actuales. Si ya coincide, la operación no lo modifica.

Para una cuenta Auth ya creada y confirmada, usar sus datos reales y añadir `--user-id UUID_DE_AUTH --apply`. En esta modalidad no se solicita ni modifica su contraseña. El correo proporcionado debe coincidir con el de Auth.

## Reanudar un alta interrumpida

Auth y los perfiles son dos servicios: no existe una transacción que incluya ambas escrituras. Si la identidad se crea y falla el perfil, la herramienta conserva la cuenta y muestra su UUID. Revisar ambos registros y reanudar con `--user-id`; no crear una segunda cuenta. Ante una interrupción de red, revisar Auth antes de repetir, porque la primera escritura podría haberse aplicado.

La herramienta no elimina cuentas ni sustituye permisos existentes. Su salida nunca muestra contraseñas, claves ni respuestas crudas del servidor. La asignación de contraseña no implementa todavía cambio obligatorio en el primer ingreso; la persona y el operador deben acordar su entrega por un canal privado.

Fuentes: [creación administrativa de usuarios](https://supabase.com/docs/reference/python/auth-admin-createuser) y [claves de Supabase](https://supabase.com/docs/guides/getting-started/api-keys).
