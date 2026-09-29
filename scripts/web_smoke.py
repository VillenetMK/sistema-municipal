"""Prueba del cliente WebAssembly en Chromium; se ejecuta en GitHub Actions.

El modo municipal comprueba Auth real con credenciales vacías y la persistencia
con respuestas interceptadas y tokens ficticios. No escribe en la base municipal.
"""

import argparse
import json
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


def check_session_reload(page, checks):
    """Ejercita almacenamiento real, reinicio de Pyodide y cierre sin credenciales reales."""
    calls = []

    def fixture(route):
        path = urlparse(route.request.url).path
        calls.append(path)
        if path == "/auth/v1/token":
            body = {
                "access_token": "browser-test-access",
                "refresh_token": "browser-test-refresh",
                "expires_in": 3600,
                "user": {"id": "browser-test-user"},
            }
        elif path == "/auth/v1/user":
            body = {"id": "browser-test-user"}
        elif path == "/auth/v1/logout":
            body = {}
        elif path == "/rest/v1/staff_profiles":
            body = [
                {
                    "user_id": "browser-test-user",
                    "display_name": "Prueba de recarga",
                    "role": "consulta",
                    "is_active": True,
                    "department_id": None,
                }
            ]
        elif path == "/rest/v1/municipal_settings":
            body = [{"institution_name": "Municipalidad de prueba"}]
        elif path == "/rest/v1/rpc/case_metrics":
            body = {"total": 0, "pending": 0, "overdue": 0, "resolved": 0}
        elif path in {"/rest/v1/departments", "/rest/v1/cases"}:
            body = []
        else:
            raise AssertionError(f"Petición inesperada en la prueba: {path}")
        route.fulfill(status=200, json=body, headers={"access-control-allow-origin": "*"})

    page.context.route("https://lxvmwjcqdjoidgpinmgm.supabase.co/**", fixture)
    page.get_by_role("textbox", name="Usuario o correo", exact=True).fill("recarga@example.invalid")
    page.get_by_role("textbox", name="Contraseña", exact=True).fill("browser-test-password")
    page.get_by_role("button", name="Ingresar", exact=True).click()
    expect(page.get_by_text("Tu jornada, en orden", exact=True)).to_be_visible()
    for _ in range(2):
        page.reload()
        page.locator("flt-semantics-placeholder").dispatch_event("click", timeout=180000)
        expect(page.get_by_text("Tu jornada, en orden", exact=True)).to_be_visible(timeout=180000)
        expect(page.get_by_text("Prueba de recarga", exact=True)).to_be_visible()
    assert calls.count("/auth/v1/token") == 1
    assert calls.count("/auth/v1/user") == 2
    checks.append("dos recargas mantienen la sesión y revalidan el perfil, con API simulada")
    page.get_by_role("button", name="Cerrar sesión", exact=True).click()
    expect(page.get_by_text("Iniciar sesión", exact=True)).to_be_visible()
    page.reload()
    page.locator("flt-semantics-placeholder").dispatch_event("click", timeout=180000)
    expect(page.get_by_text("Iniciar sesión", exact=True)).to_be_visible(timeout=180000)
    assert calls.count("/auth/v1/user") == 2
    assert calls.count("/auth/v1/logout") == 1
    checks.append("cerrar sesión y recargar exige identificarse de nuevo")
    page.context.unroute("https://lxvmwjcqdjoidgpinmgm.supabase.co/**", fixture)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["supabase", "demo"], required=True)
    parser.add_argument("--root", default="dist")
    args = parser.parse_args()
    output = Path("artifacts/web") / args.mode
    output.mkdir(parents=True, exist_ok=True)
    handler = partial(SimpleHTTPRequestHandler, directory=str(Path(args.root).resolve()))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logs, checks = [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1100}, accept_downloads=True)
            page.set_default_timeout(30000)
            page.on("console", lambda message: logs.append(f"{message.type}: {message.text}"))
            page.on("pageerror", lambda error: logs.append(f"pageerror: {error}"))
            try:
                page.goto(f"http://127.0.0.1:{server.server_port}/sistema-municipal/")
                # El control de accesibilidad de Flutter vive fuera del viewport.
                page.locator("flt-semantics-placeholder").dispatch_event("click", timeout=180000)
                if args.mode == "supabase":
                    expect(page.get_by_text("Iniciar sesión", exact=True)).to_be_visible(
                        timeout=180000
                    )
                    page.screenshot(path=output / "01-acceso.png")
                    page.get_by_role("button", name="Ingresar", exact=True).click()
                    expect(
                        page.get_by_text(re.compile("No se pudo iniciar sesión"))
                    ).to_be_visible()
                    checks.extend(
                        [
                            "inicio municipal",
                            "Fetch y Supabase Auth: rechazo de credenciales vacías",
                        ]
                    )
                    check_session_reload(page, checks)
                    page.get_by_role("button", name="Olvidé mi contraseña", exact=True).click()
                    expect(page.get_by_text("Recuperar contraseña", exact=True)).to_be_visible()
                    checks.append("recuperación de acceso")
                else:
                    page.get_by_role("button", name="Explorar demostración", exact=True).click(
                        timeout=180000
                    )
                    expect(page.get_by_text("Tu jornada, en orden", exact=True)).to_be_visible()
                    page.screenshot(path=output / "01-resumen.png")
                    checks.append("inicio y resumen demo")
                    page.get_by_role("button", name="Abrir bandeja", exact=True).click()
                    # Las fechas de los ejemplos pueden empatar: elegir un caso abierto
                    # por su asunto, sin depender del orden de UUID aleatorios.
                    search = page.get_by_role(
                        "textbox", name="Buscar por código o asunto", exact=True
                    )
                    # Flutter procesa las teclas en su propio modelo antes del envío.
                    # Un fill DOM seguido de click podía enviar aún el filtro vacío.
                    search.press_sequentially(
                        "Solicitud de información sobre una obra pública", delay=20
                    )
                    search.press("Enter")
                    expect(
                        page.get_by_role("button", name="Abrir expediente", exact=True)
                    ).to_have_count(1, timeout=30000)
                    page.get_by_role("button", name="Abrir expediente", exact=True).click()
                    with page.expect_download() as download:
                        page.get_by_role("button", name="Constancia PDF", exact=True).click()
                    receipt = output / "constancia-demo.pdf"
                    download.value.save_as(receipt)
                    from pypdf import PdfReader

                    text = "\n".join(item.extract_text() for item in PdfReader(receipt).pages)
                    assert "Constancia de registro" in text and "DEMOSTRACIÓN" in text
                    checks.append("descarga PDF con contenido comprobado")
                    with page.expect_file_chooser() as chooser:
                        page.get_by_role("button", name="Adjuntar documento", exact=True).click()
                    chooser.value.set_files(receipt)
                    # El aviso también se duplica en la región aria-live de Flutter.
                    expect(
                        page.locator("span").filter(has_text=re.compile(r"^Documento adjuntado\.$"))
                    ).to_be_visible()
                    checks.append("adjunto PDF en memoria demo")
                    page.screenshot(path=output / "02-expediente.png")
                    page.get_by_role("button", name="Expedientes", exact=True).click()
                    page.get_by_role("button", name="Reportes", exact=True).click()
                    with page.expect_download() as download:
                        page.get_by_role("button", name="CSV completo", exact=True).click()
                    csv = output / "expedientes-demo.csv"
                    download.value.save_as(csv)
                    assert csv.stat().st_size > 100
                    with page.expect_download() as download:
                        page.get_by_role("button", name="Resumen PDF", exact=True).click()
                    pdf = output / "resumen-demo.pdf"
                    download.value.save_as(pdf)
                    assert "Reporte de expedientes" in "\n".join(
                        p.extract_text() for p in PdfReader(pdf).pages
                    )
                    checks.extend(["exportación CSV", "reporte PDF"])
                    page.get_by_role("button", name="Administración", exact=True).click()
                    expect(page.get_by_text("Estado de los datos", exact=True)).to_be_visible()
                    page.get_by_role("button", name="Solicitantes", exact=True).click()
                    page.get_by_role("button", name="Editar e historial", exact=True).first.click()
                    email = page.get_by_role(
                        "textbox", name="Correo de contacto (opcional)", exact=True
                    )
                    email.fill("")
                    email.press_sequentially("contacto@example.test", delay=15)
                    reason = page.get_by_role("textbox", name="Motivo del cambio", exact=True)
                    reason.press_sequentially(
                        "Corrección ficticia de contacto en navegador.", delay=15
                    )
                    page.get_by_role("button", name="Guardar cambios", exact=True).click()
                    expect(
                        page.get_by_text(
                            "Corrección ficticia de contacto en navegador.", exact=True
                        )
                    ).to_be_visible()
                    checks.append("corrección de solicitante e historial administrativo")
                    page.screenshot(path=output / "04-solicitantes.png")
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=output / "03-movil.png")
                failures = [
                    line
                    for line in logs
                    if any(
                        term in line
                        for term in (
                            "Traceback (most recent call last)",
                            "RenderFlex overflowed",
                            "Operación de interfaz fallida",
                            "pageerror:",
                            "Error running app",
                        )
                    )
                ]
                assert not failures, "\n".join(failures)
                (output / "resultado.json").write_text(
                    json.dumps({"mode": args.mode, "checks": checks}, ensure_ascii=False, indent=2)
                )
                print(json.dumps({"mode": args.mode, "checks": checks}, ensure_ascii=False))
            except Exception:
                print("\n".join(logs[-60:]), flush=True)
                raise
            finally:
                page.screenshot(path=output / "estado-final.png")
                (output / "console.log").write_text("\n".join(logs))
                (output / "accesibilidad.yml").write_text(page.locator("body").aria_snapshot())
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
