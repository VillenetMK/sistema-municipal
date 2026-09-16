# MuniGest Chiclayo

Piloto para la **Municipalidad Provincial de Chiclayo**, orientado a mesa de partes y seguimiento interno de expedientes. Aplicación escrita en Python, interfaz Flet y backend Supabase. Repositorio de trabajo: `VillenetMK/sistema-municipal`.

Un ciudadano presenta una solicitud; Mesa de Partes la registra; un área la revisa, observa o atiende; cada actuación queda en el historial. Es el núcleo sobre el que se pueden incorporar trámites especializados.

## Lo implementado

- Inicio de sesión con Supabase Auth y autorización mediante perfiles municipales activos.
- Roles: administrador, mesa de partes, gestor de área y consulta.
- Resumen de expedientes pendientes, atendidos y con fecha objetivo interna vencida.
- Registro de solicitante, asunto, descripción, canal, prioridad y área de destino.
- Numeración anual transaccional, registro idempotente y control de versiones para evitar sobrescrituras.
- Búsqueda por código/asunto, filtros por estado y paginación.
- Derivación entre áreas; estados recibido, en revisión, observado, atendido y archivado.
- Historial generado en servidor e inmodificable desde los clientes.
- Adjuntos privados PDF, PNG y JPEG, hasta 10 MB; verificación de firma de formato y SHA-256 al descargar.
- Exportación CSV de la página visible, sin documentos de identidad y con protección ante fórmulas.
- Interfaz adaptable con navegación lateral en escritorio y menú en móvil; los estados siempre tienen texto.
- Demostración con datos ficticios aislados por sesión, sin escribir en Supabase.
- Identidad de Chiclayo, catorce gerencias verificadas y un punto de recepción para el piloto.
- Referencias al organigrama y TUPA 2026, con accesos a los portales oficiales desde el catálogo.

**Estado: base funcional para un piloto interno, versión 0.1.** La identidad institucional está configurada; falta la validación municipal de responsables, áreas operativas y fichas TUPA. Los instaladores nativos aún deben compilarse y probarse en dispositivos reales. No se ha publicado un servicio web.

Chiclayo ya dispone de mesa de partes virtual y SGD. Este piloto conserva registros internos y todavía no se sincroniza con esos servicios. Ver [configuración de Chiclayo, fuentes y alcance de la integración](docs/CHICLAYO.md).

## Ejecutar la demostración

Requisitos: Python 3.12 y Git.

```bash
git clone https://github.com/VillenetMK/sistema-municipal.git
cd sistema-municipal
python -m pip install uv==0.12.11
uv sync --frozen
uv run python run.py --web
```

Abrir `http://127.0.0.1:8550`. Elegir **Explorar demostración**. Los registros son ficticios y temporales. No se necesita una cuenta ni contraseña para el modo de demostración.

Para ejecutarlo como aplicación de escritorio:

```bash
uv sync --frozen --extra desktop
uv run python run.py
```

En Linux, el selector nativo de archivos puede requerir `zenity`. En entornos con proxy, la dependencia HTTP incluye soporte SOCKS.

## Conectar la base municipal

El proyecto municipal es **`lxvmwjcqdjoidgpinmgm`**. Su esquema inicial ya fue aplicado. La aplicación rechaza el identificador de EcoSphere para evitar confusiones.

1. Copiar `.env.example` a `.env`.
2. Configurar `MUNIGEST_MODE=supabase` y la clave **publishable** del proyecto.
3. Crear el primer usuario en Supabase Auth y autorizar su perfil con las instrucciones de [puesta en marcha](docs/PUESTA_EN_MARCHA.md).
4. Ejecutar el programa y entrar con ese usuario.

La aplicación no incluye claves secretas, contraseñas de base de datos ni credenciales `service_role`. Las sesiones se mantienen en memoria y se renuevan de forma asíncrona. Un fallo de conexión real nunca activa automáticamente la demostración.

## Plataformas

| Destino | Ejecución prevista | Estado de esta entrega |
|---|---|---|
| Web | Servidor Python de Flet | Código y arranque HTTP comprobados; despliegue pendiente |
| Windows / Linux | Cliente nativo Flet | Pantallas y lógica probadas; empaquetado y prueba de dispositivo pendientes |
| Android | APK generado con Flet | Mismo código adaptable; compilación y prueba en teléfono pendientes |
| macOS / iOS | Herramientas Flet y equipo macOS | Posibles ampliaciones; todavía sin validación de plataforma |

Las instrucciones de compilación están en [puesta en marcha](docs/PUESTA_EN_MARCHA.md). La variante web inicial usa un servidor Python; no presupone que HTTPX funcione en una exportación estática WebAssembly.

## Organización

```text
src/main.py                  Entrada del empaquetador Flet
src/munigest/ui.py            Pantallas y navegación
src/munigest/domain.py        Validaciones y reglas del flujo
src/munigest/repository.py    Sesiones, API y almacenamiento de Supabase
src/munigest/demo.py          Demostración aislada
src/munigest/config.py        Configuración y validación del proyecto
src/munigest/institution.py   Identidad de Chiclayo y referencias públicas
supabase/migrations/         Esquema, políticas RLS y operaciones transaccionales
scripts/prepare_client.py    Configuración pública para paquetes nativos
tests/                       Pruebas Python y contrato SQL
```

## Verificación

```bash
uv run pytest -q
uv run ruff check src tests scripts run.py
```

El workflow de GitHub comprueba Python y ejecuta el contrato de permisos sobre PostgreSQL 17 aislado. `tests/bootstrap_database.sql` y `tests/database_contract.sql` son exclusivamente para bases locales de prueba; no se ejecutan sobre la base municipal.

Ver [informe de validación](docs/VALIDACION.md), [alcance y decisiones](docs/ALCANCE.md) y [modelo de seguridad](docs/SEGURIDAD.md).

## Fuentes consultadas

- [Organigrama publicado de la MPCH](https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/6924346-organigrama-2024) y [organización institucional](https://www.gob.pe/institucion/munichiclayo/organizacion): selección inicial de gerencias.
- [TUPA 2026 de Chiclayo](https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/7664214-texto-unico-de-procedimientos-administrativos-tupa-vigente-2026): referencia para validar las fichas de trámites.
- [Servicios digitales de Chiclayo](https://www.munichiclayo.gob.pe/serviciosonline/): canales municipales existentes.
- [Flet](https://flet.dev/docs/): interfaz Python para web, escritorio y móvil.
- [Supabase: RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [seguridad de la API](https://supabase.com/docs/guides/api/securing-your-api) e [integración GitHub](https://supabase.com/docs/guides/deployment/branching/github-integration).

La revisión institucional se documenta en [CHICLAYO.md](docs/CHICLAYO.md). No se han precargado tarifas, requisitos ni plazos legales de trámites.
