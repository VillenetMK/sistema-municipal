# Servidor Python de MuniGest

Se incluye `Dockerfile` y `compose.yaml` para ejecutar la aplicación Flet. Esta entrega prepara el despliegue; no crea un alojamiento público ni publica una dirección web.

## Ejecución sin Docker

Con las variables de [puesta en marcha](PUESTA_EN_MARCHA.md) configuradas:

```bash
uv sync --frozen --no-dev --extra server
uv run --no-sync python run.py --web --host 0.0.0.0 --port 8550
```

También se acepta la variable `PORT`, habitual en proveedores de alojamiento. `--port` tiene prioridad frente a `PORT`. Flet reconoce adicionalmente sus propias variables `FLET_SERVER_PORT` y `FLET_SERVER_IP`; mantenerlas sin definir cuando se utiliza la configuración anterior.

El servidor valida la configuración antes de abrir el puerto. La aplicación web conserva una sesión y repositorio separados por conexión. Las sesiones viven en memoria: inicialmente se utiliza una instancia; reiniciarla requiere que los usuarios vuelvan a ingresar.

## Ejecución con Docker Compose

Configurar únicamente la clave publicable municipal en `.env`, según `.env.example`, y ejecutar desde la raíz:

```bash
docker compose up --build -d
docker compose logs --tail 50 municipal
```

Abrir `http://127.0.0.1:8550`. Compose usa el proyecto municipal y modo Supabase, exige la clave publicable y expone el puerto solo en el equipo anfitrión. El proceso del contenedor se ejecuta sin privilegios de administrador y su sistema de archivos es de solo lectura, salvo temporales y el directorio de trabajo del usuario.

El contexto de construcción excluye credenciales, herramientas administrativas y configuración nativa generada. No pasar `SUPABASE_SECRET_KEY` a este servidor: los accesos a los expedientes utilizan la clave publicable y la sesión de cada trabajador.

Para un proveedor que construya el Dockerfile, configurar las mismas variables públicas e indicar que acepte WebSocket. El proveedor debe terminar HTTPS. La comprobación de salud de la imagen comprueba que se sirve la página inicial; no certifica conectividad con Supabase ni una sesión válida.

## Estado de verificación

El arranque Python se comprueba localmente sirviendo la página de Flet por HTTP. La imagen Docker aún requiere construcción y prueba en un equipo con Docker; el entorno de desarrollo actual no tiene ese motor. No se ha contratado alojamiento ni configurado dominio o certificado.

Referencia: [Flet como aplicación web dinámica](https://flet.dev/docs/publish/web/dynamic-website/).
