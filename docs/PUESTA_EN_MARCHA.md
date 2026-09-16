# Puesta en marcha

## 1. Confirmar el destino

Proyecto municipal: `lxvmwjcqdjoidgpinmgm`.

Panel: https://supabase.com/dashboard/project/lxvmwjcqdjoidgpinmgm

El esquema inicial está aplicado y registrado en `supabase/migrations/`. No volver a ejecutarlo manualmente en ese proyecto. Antes de futuros cambios, comprobar la identidad del proyecto y el historial de migraciones. El proyecto de EcoSphere es independiente.

## 2. Configurar la aplicación

Copiar `.env.example` a `.env`, en la raíz del repositorio. En Windows se puede copiar desde el Explorador; en una terminal Python:

```bash
python -c "import shutil; shutil.copyfile('.env.example', '.env')"
```

Usar:

```dotenv
MUNIGEST_MODE=supabase
MUNIGEST_NAME=MuniGest
SUPABASE_PROJECT_REF=lxvmwjcqdjoidgpinmgm
SUPABASE_URL=https://lxvmwjcqdjoidgpinmgm.supabase.co
SUPABASE_PUBLISHABLE_KEY=TU_CLAVE_PUBLICABLE
```

Obtener la clave **publishable** desde las claves API del proyecto. No introducir `service_role`, una clave `sb_secret`, la contraseña de PostgreSQL o un token personal. `.env` está excluido de Git.

## 3. Primer administrador

La aplicación no crea administradores por orden de registro. Una cuenta de Supabase Auth, por sí sola, no concede acceso al sistema.

1. Crear el usuario autorizado desde el panel de Supabase Auth, con su correo real y el mecanismo de acceso acordado con la entidad.
2. En el editor SQL **del proyecto municipal**, sustituir el correo y el nombre en este bloque. Ejecutarlo una vez. No dejar los marcadores de ejemplo.

```sql
DO $$
DECLARE
  target_user uuid;
  target_department uuid;
BEGIN
  SELECT id INTO target_user FROM auth.users
    WHERE lower(email) = lower('TU_CORREO_INSTITUCIONAL');
  IF target_user IS NULL THEN
    RAISE EXCEPTION 'Primero crea y verifica el usuario en Supabase Auth';
  END IF;
  SELECT id INTO target_department FROM public.departments WHERE code = 'MP';
  INSERT INTO public.staff_profiles(user_id, display_name, role, department_id, is_active)
    VALUES (target_user, 'TU_NOMBRE_COMPLETO', 'admin', target_department, true);
END $$;
```

No se ejecutó este bloque durante el desarrollo: el titular y la cuenta administrativa deben ser reales y estar identificados. No hay contraseñas de prueba ni usuarios privilegiados precargados.

Para cada trabajador, crear su cuenta Auth y un `staff_profiles` con el rol y área correspondientes. Los perfiles inactivos quedan bloqueados incluso si conservan un JWT todavía válido. La asignación de perfiles en esta primera versión se realiza desde Supabase, no desde una pantalla administrativa.

## 4. Datos institucionales

Actualizar `municipal_settings` con el nombre real, ubigeo y `configured=true` una vez validados. Adaptar `departments` al organigrama. Mantener los códigos únicos y desactivar áreas antiguas sin borrar su historial. Incorporar a `procedures` únicamente trámites verificados: `is_official=true` exige una referencia normativa en `legal_basis`.

La opción Solicitud general es una referencia inicial. No tiene tarifa o plazo legal precargados. Los cambios de estos catálogos en v0.1 se realizan desde Supabase.

## 5. Ejecutar

```bash
uv sync --frozen
uv run python run.py --web
```

Para otra máquina de una red de pruebas autorizada:

```bash
uv run python run.py --web --host 0.0.0.0 --port 8550
```

El uso público necesita alojamiento Python, HTTPS y soporte de WebSocket. Esta entrega no despliega un servidor ni publica un dominio. La integración GitHub de Supabase aplica migraciones; no aloja la aplicación Flet.

## 6. Empaquetado nativo

El script siguiente lee `.env`, valida el proyecto y genera un módulo local ignorado por Git con configuración pública. No contiene contraseñas ni claves secretas.

```bash
uv run python scripts/prepare_client.py --mode demo
uv run flet build apk
```

Para un cliente real, después de configurar `.env`:

```bash
uv run python scripts/prepare_client.py --mode supabase
uv run flet build apk
```

Windows se compila en Windows:

```bash
uv run flet build windows
```

Linux se compila en Linux:

```bash
uv run flet build linux
```

Flet puede solicitar Flutter, Android SDK, Java y herramientas nativas. Las compilaciones para distribución oficial requieren la identidad de paquete y firma administradas por la entidad. No se generaron certificados ni instaladores oficiales en esta entrega. Antes de cada compilación, volver a ejecutar `prepare_client.py` con el modo correcto; una compilación sin ese módulo usa demostración por defecto.

## 7. Validar el piloto

Probar con usuarios de dos áreas: registro, derivación, observación, atención, archivo y adjuntos. Comprobar recepción de archivos en web, Windows y Android reales. Validar el acceso con cuentas de consulta e inactivas. Definir la política de conservación de documentos, respaldo y recuperación con el responsable municipal antes de usar información real.

El sistema no realiza envío automático de notificaciones, firma digital, análisis antivirus de adjuntos ni sincronización sin conexión. Esas capacidades deben incorporarse según el procedimiento oficial que se elija.
