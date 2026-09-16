# MuniGest — Sistema Municipal

Primera versión funcional para **mesa de partes y seguimiento interno de expedientes**. Aplicación escrita en Python, interfaz Flet y backend Supabase. Repositorio de trabajo: `VillenetMK/sistema-municipal`.

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

**Estado: base funcional para un piloto interno, versión 0.1.** Todavía requiere configurar la municipalidad, los usuarios autorizados y su TUPA antes de uso oficial. Los instaladores nativos aún deben compilarse y probarse en dispositivos reales. No se ha publicado un servicio web.

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

- [Mesa de partes de la Municipalidad de San Isidro](https://www.gob.pe/20823-municipalidad-distrital-de-san-isidro-lima-acceder-a-mesa-de-partes): ejemplo real de recepción de documentos.
- [Trámites y servicios de San Isidro](https://www.gob.pe/institucion/munisanisidro-lima/tramites-y-servicios): mesa de partes, seguimiento y TUPA.
- [Flet](https://flet.dev/docs/): interfaz Python para web, escritorio y móvil.
- [Supabase: RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [seguridad de la API](https://supabase.com/docs/guides/api/securing-your-api) e [integración GitHub](https://supabase.com/docs/guides/deployment/branching/github-integration).

Los ejemplos de otra entidad orientan el diseño; sus tarifas, requisitos y plazos no se trasladan a esta municipalidad.
