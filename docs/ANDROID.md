# MuniGest Chiclayo en Android

## Instalar en el teléfono

Las compilaciones que pasan las pruebas se publican como versiones piloto en
[Releases](https://github.com/VillenetMK/sistema-municipal/releases).

Versión comprobada el 23/09/2026: [Android piloto 4](https://github.com/VillenetMK/sistema-municipal/releases/tag/android-piloto-4), aproximadamente 67 MB. Ambas variantes aprobaron la [ejecución de Android](https://github.com/VillenetMK/sistema-municipal/actions/runs/35880312397).

1. Abre la versión **MuniGest Chiclayo · Android piloto** y descarga
   `MuniGest-Chiclayo-supabase.apk` desde **Assets**.
2. Abre la descarga. Si Android lo solicita, autoriza a ese navegador o gestor de
   archivos para instalar aplicaciones y vuelve a abrir el APK.
3. Abre **MuniGest Chiclayo**. Usa el mismo usuario y contraseña de la aplicación
   de PC. La cuenta administradora del piloto admite el alias `admin`.

El APK lleva la configuración pública del proyecto municipal
`lxvmwjcqdjoidgpinmgm`; no hay que copiar `.env` al teléfono. No lleva contraseñas
ni una clave administrativa. Cada operación necesita la sesión y los permisos
del usuario. Requiere Internet; no existe sincronización sin conexión.

Es un APK universal para Android 7 o posterior, con ARM64, ARM de 32 bits y
x86_64. El menú **Abrir menú** permite pasar de una sección a otra en pantallas
pequeñas. **Constancia PDF**, las descargas y **Adjuntar documento** abren el
selector de archivos de Android; no requieren acceso general a todos los archivos.

## Alcance de la firma

Estas primeras compilaciones usan la firma de pruebas de Flet/Android y se
instalan directamente. No están publicadas en Google Play. Si una nueva
compilación se firma con otra clave, Android puede exigir desinstalar la anterior.
La información registrada permanece en Supabase; los archivos descargados quedan
en la ubicación elegida en el teléfono. Al cerrar la aplicación se pierde la
sesión en memoria y será necesario volver a iniciar sesión.

Antes de distribuir una versión estable, el responsable del proyecto debe
conservar una clave de firma propia. Flet acepta `FLET_ANDROID_SIGNING_KEY_STORE`,
`FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD`, `FLET_ANDROID_SIGNING_KEY_PASSWORD` y
`FLET_ANDROID_SIGNING_KEY_ALIAS`. La clave y las contraseñas no se guardan en Git
ni dentro de `src/`.

## Compilar desde VS Code en Windows

Android Studio puede aportar el SDK y un emulador; el código sigue en este
repositorio Python. Se necesita JDK 17. Flet puede descargar su versión de Flutter.

En la terminal PowerShell de la carpeta `sistema-municipal`:

```powershell
git pull --ff-only origin main
py -3.12 -m uv sync --frozen
py -3.12 scripts/setup_env.py
py -3.12 -m uv run python scripts/prepare_client.py --mode supabase
py -3.12 -m uv run flet build apk --yes --python-version 3.13
```

El APK queda en `build/apk/`. El Python que ejecuta el compilador en Windows es
3.12; el intérprete empaquetado para Android es 3.13. Se puede instalar directamente
en un emulador abierto en Android Studio:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r .\build\apk\app-release.apk
```

Usa el nombre concreto del APK que indique la compilación si difiere. Para ver
fallos de Python en el dispositivo conectado:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" logcat -s flet.python
```

## Pruebas reproducibles

[APK Android](../.github/workflows/android.yml) compila dos variantes:

| Variante | Identificador | Comprobación |
|---|---|---|
| Cliente municipal | `pe.munigest.chiclayo` | Instalación, apertura, conexión TLS/Auth con acceso vacío rechazado, formularios públicos |
| Demostración aislada | `pe.munigest.chiclayo.demo` | Navegación, expediente, PDF con contenido comprobado, guardado y adjunto con el selector del sistema |

La variante demo solo conserva datos ficticios en memoria. El flujo automatizado
no introduce expedientes en Supabase ni usa cuentas privadas. Las pruebas se
ejecutan en un emulador Android 15 x86_64; el APK municipal comprobado es el mismo
archivo universal que se publica. El trabajo de publicación depende del éxito
de ambas variantes.

Cada ejecución conserva APK, suma SHA-256, capturas, árboles de accesibilidad,
resultado JSON y logcat en sus artefactos durante 30 días. Los APK publicados en
Releases permanecen disponibles después de ese período.

En un teléfono físico falta comprobar con una cuenta válida: acceso al área
autorizada, registro/consulta de un expediente permitido, adjunto y descarga,
rotación y respuesta al perder/restablecer la conexión. La prueba automatizada
no sustituye esa comprobación ni la validación de uso municipal.

## Referencias

- [Flet: empaquetado Android, firma, permisos y paquetes extraídos](https://flet.dev/docs/publish/android/).
- [Android Emulator Runner](https://github.com/ReactiveCircus/android-emulator-runner).
