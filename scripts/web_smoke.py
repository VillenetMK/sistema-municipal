"""Prueba del cliente WebAssembly en Chromium; se ejecuta en GitHub Actions.

El modo municipal solo comprueba el rechazo de credenciales vacías. Los archivos
y expedientes de prueba pertenecen exclusivamente al modo demo, en memoria.
"""

import argparse
import json
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


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
                    page.get_by_role("button", name="Abrir expediente", exact=True).first.click()
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
                    expect(page.get_by_text("Documento adjuntado", exact=True)).to_be_visible()
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
