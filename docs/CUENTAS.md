# Usuarios e invitaciones

El administrador crea cuentas desde **Administración → Personal → Usuarios e invitaciones → Crear usuario**. Indica nombre, correo real, rol, área y motivo. La base verifica que el administrador y el área sigan activos.

1. Crear la invitación y entregar su código por un canal privado a esa persona. Dura 48 horas. El sistema conserva solo su huella; si se pierde, revocar la invitación y crear otra.
2. La persona abre **Activar invitación** en el inicio de sesión, escribe su correo y código, y elige su contraseña (al menos 12 caracteres). El administrador no conoce esa contraseña.
3. En **Confirmar mi correo**, pegar el enlace original del botón del correo, copiado sin abrirlo. También se admite el código numérico si la plantilla de correo lo incluye. Después, iniciar sesión normalmente.
4. Si el correo no llega, solicitar un reenvío desde esa pantalla. Revisar spam y la configuración de correo descrita abajo.

Crear una invitación no envía correo automáticamente. El mensaje de confirmación lo solicita la persona al activar la cuenta. La lista muestra fechas de vencimiento, activación y revocación. Una invitación activada ya tiene perfil: para retirarle acceso, desactivar ese perfil en Personal.

Las cuentas existentes se administran en **Personal → Editar e historial**. El alta autorizada por invitación crea identidad y perfil en la misma transacción del servidor. Los permisos proceden de la invitación privada, nunca del rol enviado en `user_metadata`. Un registro Auth sin invitación no obtiene un perfil municipal ni acceso a los expedientes. La herramienta de [alta operativa](USUARIOS.md) sigue disponible para cuentas creadas por el operador.

## Recuperación de contraseña

En el inicio de sesión, elegir **Olvidé mi contraseña**, indicar el correo y solicitar el mensaje. Pegar el enlace original de recuperación o su código, escribir dos veces la nueva contraseña y guardar. El programa verifica que el enlace corresponda al proyecto municipal y a recuperación; usa una sesión transitoria para actualizar la contraseña y la cierra. La pantalla no confirma si un correo particular existe.

Las cuatro cuentas piloto usan `.invalid`: no reciben correo. Para ellas, el operador puede cambiar la contraseña desde Supabase Auth. No se cambió la contraseña actual de `admin` en esta entrega.

## Configuración de correo necesaria

En el proyecto municipal, habilitar registro por correo y confirmación de correo. La configuración local del repositorio conserva esa misma política. En producción, configurar SMTP propio antes de dar de alta personal externo: el proveedor predeterminado de Supabase limita destinatarios y frecuencia. Mantener el enlace `ConfirmationURL` de las plantillas o incluir el código `Token`; no sustituirlo por un enlace de otro proyecto.

El flujo de esta versión permite copiar el enlace original dentro de la aplicación Python, sin depender de enlaces profundos de Android ni de un sitio web publicado. Abrir el enlace en el navegador puede consumirlo antes de pegarlo; si sucede, pedir otro correo.

A fecha 23/09/2026 se verificó que Auth admite registro por correo y exige confirmación en el proyecto municipal. No se configuraron credenciales SMTP ni se realizó una entrega real a un buzón externo. Las pruebas de envío/verificación usan respuestas simuladas; las reglas de invitación se probaron sobre PostgreSQL y los permisos de lectura sobre las cuentas reales del piloto.

## Acceso del compañero de base de datos

Una cuenta de la aplicación y un miembro de Supabase son accesos distintos. El compañero que administra la base necesita una invitación del equipo de la organización **Sistema Municipal**, con rol **Developer**. El proyecto municipal es `lxvmwjcqdjoidgpinmgm`; EcoSphere pertenece a otra organización y no debe incluirse. En el plan Free el rol abarca la organización; los roles limitados a un solo proyecto requieren un plan que los soporte. La persona acepta la invitación desde su propio correo.

Referencias oficiales: [registro y recuperación por correo](https://supabase.com/docs/guides/auth/passwords), [SMTP](https://supabase.com/docs/guides/auth/auth-smtp), [roles del equipo](https://supabase.com/docs/guides/platform/access-control).
