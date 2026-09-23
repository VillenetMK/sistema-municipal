"""Prueba del APK instalado mediante ADB; solo el modo demo modifica expedientes.

Ejecutar con un emulador Android 15 en inglés, ya encendido. Guarda capturas,
árboles de accesibilidad y logcat incluso cuando falla. No necesita credenciales.
"""

import argparse
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

OUTPUT = Path("artifacts/android")


def adb(*args, binary=False, check=True):
    result = subprocess.run(
        ["adb", *args], capture_output=True, text=not binary, timeout=40, check=check
    )
    return result.stdout


def hierarchy():
    adb("shell", "uiautomator", "dump", "/sdcard/munigest-ui.xml", check=False)
    raw = adb("exec-out", "cat", "/sdcard/munigest-ui.xml", check=False)
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        return ET.Element("hierarchy")


def label(node):
    return " ".join([node.get("text", ""), node.get("content-desc", "")]).strip()


def find(text, *, timeout=35, scroll=False):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root = hierarchy()
        if any("Error running app" in label(n) for n in root.iter("node")):
            capture("fallo-arranque")
            raise AssertionError("El APK muestra un error de arranque; revisar logcat.")
        matches = [
            n
            for n in root.iter("node")
            if text.casefold() in label(n).casefold() and n.get("enabled") != "false"
        ]
        if matches:
            # Elegir el nodo más específico si Android combina varias etiquetas.
            return min(matches, key=lambda n: len(label(n)))
        if scroll:
            adb("shell", "input", "swipe", "500", "1500", "500", "500", "350")
        time.sleep(0.5)
    capture("fallo")
    raise AssertionError(f"No se encontró en Android: {text}")


def tap(text, **kwargs):
    node = find(text, **kwargs)
    print(f"Android: {text}", flush=True)
    bounds = [int(n) for n in re.findall(r"\d+", node.get("bounds", ""))]
    if len(bounds) != 4 or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        raise AssertionError(f"Control sin superficie visible: {text}")
    adb(
        "shell",
        "input",
        "tap",
        str((bounds[0] + bounds[2]) // 2),
        str((bounds[1] + bounds[3]) // 2),
    )
    time.sleep(0.7)


def capture(name):
    print(f"Captura: {name}", flush=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f"{name}.png").write_bytes(adb("exec-out", "screencap", "-p", binary=True))
    ET.ElementTree(hierarchy()).write(OUTPUT / f"{name}.xml", encoding="utf-8")


def menu(destination):
    tap("Abrir menú")
    tap(destination)


def demo_checks():
    tap("Explorar demostración", timeout=90)
    find("DEMOSTRACIÓN")
    capture("02-resumen")
    menu("Áreas y trámites")
    find("Catálogo", scroll=True)
    capture("03-catalogo")
    menu("Expedientes")
    tap("Abrir expediente", scroll=True, timeout=65)
    # Abrir un expediente restablece la posición, aunque la bandeja estuviera abajo.
    find("Constancia PDF")
    capture("04-expediente")
    tap("Constancia PDF")
    find("Save", timeout=45)
    capture("05-selector-guardar")
    tap("Save")
    time.sleep(1)
    saved = adb("shell", "find", "/sdcard/Download", "-name", "constancia_*.pdf").strip()
    if not saved:
        raise AssertionError("Android no guardó la constancia en Descargas.")
    receipt = OUTPUT / "constancia-demo.pdf"
    adb("pull", saved.splitlines()[0], str(receipt))
    from pypdf import PdfReader

    contents = "\n".join(page.extract_text() for page in PdfReader(receipt).pages)
    if "DEMOSTRACIÓN" not in contents or "Constancia de registro" not in contents:
        raise AssertionError("El PDF guardado no contiene la constancia de demostración.")
    # Adjuntar el PDF recién generado usando el selector nativo.
    tap("Adjuntar documento", scroll=True, timeout=65)
    capture("06-selector-adjuntar")
    tap("constancia_", timeout=45)
    find("Documento adjuntado", timeout=25)
    find("constancia_", scroll=True, timeout=65)
    capture("07-documento-adjunto")
    tap("Cerrar sesión")
    find("Explorar demostración")
    return [
        "inicio",
        "demo",
        "menú",
        "catálogo",
        "expediente",
        "constancia PDF",
        "guardar archivo",
        "adjuntar archivo",
        "cerrar sesión",
    ]


def supabase_checks():
    # UIAutomator no incluye las etiquetas flotantes de los EditText de Flutter.
    # Esperar el título y comprobar ambos campos nativos, incluido el protegido.
    find("Iniciar sesión", timeout=90)
    find("Ingresar", scroll=True)
    fields = [n for n in hierarchy().iter("node") if n.get("class") == "android.widget.EditText"]
    if len(fields) != 2 or sum(n.get("password") == "true" for n in fields) != 1:
        capture("fallo-campos-acceso")
        raise AssertionError("El acceso debe mostrar usuario y contraseña protegida.")
    capture("02-inicio-supabase")
    # Una petición sin credenciales verifica TLS/Auth sin entrar en cuentas reales.
    tap("Ingresar", scroll=True)
    find("No se pudo iniciar sesión", timeout=35, scroll=True)
    capture("03-validacion-auth")
    tap("Olvidé mi contraseña", scroll=True)
    find("Recuperar contraseña")
    capture("04-recuperacion")
    tap("Volver al inicio de sesión", scroll=True)
    tap("Activar invitación", scroll=True)
    find("Activar una invitación")
    capture("05-invitacion")
    tap("Volver al inicio de sesión", scroll=True)
    return ["inicio", "TLS y rechazo de acceso vacío", "recuperación", "invitación"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["supabase", "demo"], required=True)
    parser.add_argument("--apk", type=Path, required=True)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    package = "pe.munigest.chiclayo" + (".demo" if args.mode == "demo" else "")
    report = {"mode": args.mode, "package": package, "status": "failed"}
    try:
        adb("wait-for-device")
        adb("install", "-r", str(args.apk))
        adb("logcat", "-c")
        adb("shell", "am", "force-stop", package)
        adb("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
        report["checks"] = demo_checks() if args.mode == "demo" else supabase_checks()
        capture("08-final")
        if not adb("shell", "pidof", package).strip():
            raise AssertionError("El proceso Android terminó durante la prueba.")
        logs = adb("logcat", "-d", "-s", "flet.python", "flutter", "AndroidRuntime")
        for marker in [
            "Traceback (most recent call last)",
            "FATAL EXCEPTION",
            "RenderFlex overflowed",
            "Operación de interfaz fallida",
        ]:
            if marker in logs:
                raise AssertionError(f"Fallo en logcat: {marker}")
        report["status"] = "passed"
    finally:
        (OUTPUT / "logcat.txt").write_text(
            adb("logcat", "-d", "-s", "flet.python", "flutter", "AndroidRuntime", check=False),
            encoding="utf-8",
        )
        (OUTPUT / "resultado.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
