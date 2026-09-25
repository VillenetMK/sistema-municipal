# MuniGest Chiclayo
### Gestión de expedientes · Piloto en Python

Aplicación para registrar solicitudes, derivarlas entre áreas y consultar el historial de cada expediente. Incluye una demostración con datos ficticios para explorar el flujo sin una cuenta.

| En un vistazo | Detalle |
|---|---|
| Problema | Dar seguimiento al recorrido de una solicitud y a las actuaciones de cada área |
| Tecnologías | Python, Flet, Supabase y PostgreSQL |
| Funciones | Roles, bandejas, derivaciones, historial, adjuntos y reportes |
| Demostración | Local, con registros ficticios aislados por sesión |
| Estado | Piloto interno 0.1; APK Android publicado; validación municipal y despliegue del servicio pendientes |

**Explorar:** [ejecutar la demostración](#ejecutar-la-demostración) · [alcance](docs/ALCANCE.md) · [validación](docs/VALIDACION.md) · [modelo de seguridad](docs/SEGURIDAD.md)

Este repositorio presenta un piloto orientado a la Municipalidad Provincial de Chiclayo. No acredita una implementación oficial ni sustituye sus servicios digitales existentes.

---

Piloto para la **Municipalidad Provincial de Chiclayo**, orientado a mesa de partes y seguimiento interno de expedientes. Aplicación escrita en Python, interfaz Flet y backend Supabase. Repositorio de trabajo: `VillenetMK/sistema-municipal`.

Un ciudadano presenta una solicitud; Mesa de Partes la registra; un área la revisa, observa o atiende; cada actuación queda en el historial. Es el núcleo sobre el que se pueden incorporar trámites especializados.

## Lo implementado

- Inicio de sesión con Supabase Auth y autorización mediante perfiles municipales activos.
- Roles: administrador, mesa de partes, gestor de área y consulta.
- Resumen de expedientes pendientes, atendidos y con fecha objetivo interna vencida.
- Registro de solicitante, asunto, descripción, canal, prioridad, trámite, área de destino y responsable opcional.
- Copia histórica de la ficha del trámite; cambios de responsable, prioridad y fecha objetivo con motivo e historial.
- Numeración anual transaccional, registro idempotente y control de versiones para evitar sobrescrituras.
- Bandeja con Mis pendientes, Sin responsable y Objetivo hoy; filtros por estado, área, trámite, responsable, prioridad, ingreso y objetivo interno, con paginación.
- Derivación entre áreas que libera al responsable anterior; estados recibido, en revisión, observado, atendido y archivado.
- Historial generado en servidor e inmodificable desde los clientes.
- Adjuntos privados PDF, PNG y JPEG, hasta 10 MB; verificación de firma de formato y SHA-256 al descargar.
- Exportación CSV de la página visible, con trámite y responsable, sin documentos de identidad y con protección ante fórmulas.
- Constancia de registro PDF por expediente, con identidad parcial y situación al emitir la copia.
- Reportes completos de los resultados filtrados: CSV e indicadores PDF por estado, prioridad y área; corte consistente, permisos por área y límite explícito de 10000 resultados.
- Interfaz adaptable con navegación lateral en escritorio y menú en móvil; los estados siempre tienen texto.
- Diseño renovado con sección activa, indicadores con iconos, formularios alineados y filtros avanzados desplegables. [Ver capturas y revisión del diseño](docs/DISENO.md).
- Demostración con datos ficticios aislados por sesión, sin escribir en Supabase.
- Identidad de Chiclayo, catorce gerencias verificadas y un punto de recepción para el piloto.
- Referencias al organigrama y TUPA 2026, con accesos a los portales oficiales desde el catálogo.

**Estado: base funcional para un piloto interno, versión 0.1.** La identidad institucional está configurada; falta la validación municipal de responsables, áreas operativas y fichas TUPA. El APK piloto de Android ya está compilado, probado en emulador y publicado; falta comprobarlo en un teléfono físico con una cuenta válida. Los instaladores de escritorio y el servicio web siguen pendientes.

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

## Actualizar desde GitHub en Windows

Abrir en VS Code la carpeta clonada `sistema-municipal`. Cerrar la aplicación antes de actualizar y ejecutar estos comandos, uno por uno, en la terminal de esa carpeta:

```powershell
git pull --ff-only origin main
py -3.12 -m uv sync --frozen --extra desktop
py -3.12 -m uv run python run.py
```

GitHub conserva el código y VS Code trabaja sobre la copia local. No hace falta exportar archivos ni instalar una extensión de IA para este flujo. La configuración `.env` se mantiene en cada equipo y está excluida del repositorio. Si Git informa cambios locales incompatibles, conservarlos y resolverlos antes de repetir la actualización.

## Conectar la base municipal

El proyecto municipal es **`lxvmwjcqdjoidgpinmgm`**. Su esquema inicial ya fue aplicado. La aplicación rechaza el identificador de EcoSphere para evitar confusiones.

Crear el archivo local desde la terminal de VS Code en Windows:

```powershell
py -3.12 scripts/setup_env.py
py -3.12 -m uv run python run.py
```

El primer comando crea `.env` junto a `run.py`, con el modo Supabase, la URL municipal y su clave **publishable** ya preparados. Si el archivo existe, lo conserva sin cambios. En Linux o macOS se puede ejecutar `python scripts/setup_env.py`.

Entrar con una de las cuentas de prueba ya entregadas para el piloto, o crear una cuenta individual siguiendo la [puesta en marcha](docs/PUESTA_EN_MARCHA.md). La clave publicable identifica el proyecto; cada operador necesita su propia cuenta autorizada.

Para la cuenta administradora del piloto, escribir `admin` en **Usuario o correo** y usar la contraseña entregada por separado. El correo completo también sigue siendo válido.

Se crearon y probaron cuatro cuentas del piloto, una por rol; sus credenciales se entregaron fuera del repositorio. Para crear cuentas individuales se incluyen [invitaciones desde la aplicación](docs/CUENTAS.md) y una [herramienta operativa de alta](docs/USUARIOS.md). El [despliegue del servidor](docs/DESPLIEGUE.md) incluye Dockerfile y Compose. Las cuentas de trabajadores reales y la publicación del servicio siguen pendientes.

La aplicación no incluye claves secretas, contraseñas de base de datos ni credenciales `service_role`. Las sesiones se mantienen en memoria y se renuevan de forma asíncrona. Un fallo de conexión real nunca activa automáticamente la demostración.

## Plataformas

| Destino | Ejecución prevista | Estado de esta entrega |
|---|---|---|
| Web | Servidor Python de Flet | Código y arranque HTTP comprobados; despliegue pendiente |
| Windows / Linux | Cliente nativo Flet | Lógica probada y capturas del cliente Linux revisadas a 390 y 1280 píxeles; empaquetado y comprobación en Windows pendientes |
| Android | APK universal generado con Flet | Publicado y probado en emulador Android 15; prueba en teléfono físico pendiente |
| macOS / iOS | Herramientas Flet y equipo macOS | Posibles ampliaciones; todavía sin validación de plataforma |

Las instrucciones de compilación están en [puesta en marcha](docs/PUESTA_EN_MARCHA.md). La variante web inicial usa un servidor Python; no presupone que HTTPX funcione en una exportación estática WebAssembly.

**Android:** [descargar el APK piloto](https://github.com/VillenetMK/sistema-municipal/releases/tag/android-piloto-8) y consultar la [guía de instalación, firma y pruebas](docs/ANDROID.md). Lleva la configuración pública municipal; no se copia `.env` al teléfono. Las pruebas de PDF y adjuntos usan una demostración aislada; el cliente municipal comprueba arranque, conexión Auth y formularios públicos.

## Organización

El módulo [Administración](docs/ADMINISTRACION.md) permite gestionar áreas, fichas de trámites y los roles, áreas y estados de cuentas existentes. Cada cambio conserva motivo y versiones anterior y posterior. Se muestra únicamente a administradores y la base vuelve a verificar el permiso en cada operación.

La guía de [expedientes y bandeja de trabajo](docs/EXPEDIENTES.md) explica cómo vincular trámites, asignar responsables y organizar pendientes.

La guía de [constancias y reportes](docs/REPORTES.md) explica las descargas PDF y CSV, los indicadores y el alcance de cada cuenta.

La guía de [cuentas e invitaciones](docs/CUENTAS.md) explica el alta desde Administración y la recuperación de contraseña por correo. La guía de [respaldos](docs/RESPALDOS.md) incluye copia cifrada de datos y adjuntos, verificación y ensayo de restauración en una base local vacía.

```text
src/main.py                  Entrada del empaquetador Flet
src/munigest/ui.py            Pantallas y navegación
src/munigest/design.py        Tema, contraste y componentes visuales comunes
src/munigest/admin_ui.py      Administración de catálogos y perfiles
src/munigest/administration.py Validaciones de Administración
src/munigest/work_ui.py       Bandeja y organización de expedientes
src/munigest/work_queue.py    Filtros y fechas objetivo internas
src/munigest/report_ui.py     Pantalla de reportes y descargas
src/munigest/reports.py       Filtros, indicadores y CSV completo
src/munigest/pdf_exports.py   Constancias y resúmenes PDF
src/munigest/domain.py        Validaciones y reglas del flujo
src/munigest/repository.py    Sesiones, API y almacenamiento de Supabase
src/munigest/demo.py          Demostración aislada
src/munigest/config.py        Configuración y validación del proyecto
src/munigest/institution.py   Identidad de Chiclayo y referencias públicas
supabase/migrations/         Esquema, políticas RLS y operaciones transaccionales
scripts/prepare_client.py    Configuración pública para paquetes nativos
scripts/setup_env.py         Crea .env local sin sobrescribirlo
tests/                       Pruebas Python y contrato SQL
```

## Verificación

```bash
uv run --group operations pytest -q
uv run ruff check src tests scripts run.py
```

El workflow de GitHub comprueba Python, captura veinte pantallas del cliente nativo y ejecuta los contratos de permisos sobre PostgreSQL 17 aislado. Los scripts SQL de `tests/` son exclusivamente para bases locales de prueba; no se ejecutan sobre la base municipal.

Ver [informe de validación](docs/VALIDACION.md), [alcance y decisiones](docs/ALCANCE.md) y [modelo de seguridad](docs/SEGURIDAD.md).

## Fuentes consultadas

- [Organigrama publicado de la MPCH](https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/6924346-organigrama-2024) y [organización institucional](https://www.gob.pe/institucion/munichiclayo/organizacion): selección inicial de gerencias.
- [TUPA 2026 de Chiclayo](https://www.gob.pe/institucion/munichiclayo/informes-publicaciones/7664214-texto-unico-de-procedimientos-administrativos-tupa-vigente-2026): referencia para validar las fichas de trámites.
- [Servicios digitales de Chiclayo](https://www.munichiclayo.gob.pe/serviciosonline/): canales municipales existentes.
- [Flet](https://flet.dev/docs/): interfaz Python para web, escritorio y móvil.
- [Supabase: RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [seguridad de la API](https://supabase.com/docs/guides/api/securing-your-api) e [integración GitHub](https://supabase.com/docs/guides/deployment/branching/github-integration).

La revisión institucional se documenta en [CHICLAYO.md](docs/CHICLAYO.md). No se han precargado tarifas, requisitos ni plazos legales de trámites.
