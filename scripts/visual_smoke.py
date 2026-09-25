"""Capturas de la interfaz nativa con datos ficticios, sin conexión a Supabase.

Ejecutar en Linux con una pantalla disponible, por ejemplo mediante xvfb-run.
Las capturas proceden de Flutter/Flet; no son maquetas HTML de la aplicación.
"""

import asyncio
import json
import traceback
from pathlib import Path

import flet as ft

from munigest.account_ui import AccountScreen
from munigest.config import Settings
from munigest.demo import DemoRepository
from munigest.report_ui import show_report
from munigest.ui import MunicipalApp

OUTPUT = Path("artifacts/design")
failure = None
captures = []


async def main(page: ft.Page):
    global failure
    app = None
    try:
        page.enable_screenshots = True
        page.window.width, page.window.height = 1280, 960
        page.window.left = page.window.top = 0
        page.update()
        await asyncio.sleep(1)
        for width, height, label in [(1280, 960, "desktop"), (390, 844, "mobile")]:
            page.window.width, page.window.height = width, height
            page.update()
            for _ in range(30):
                if page.width and abs(page.width - width) < 30:
                    break
                await asyncio.sleep(0.1)
            assert page.width and abs(page.width - width) < 30, page.width

            async def capture(name, viewport=label):
                page.update()
                # Dejar terminar la animación del tema y el primer layout.
                await asyncio.sleep(0.6)
                data = await asyncio.wait_for(page.take_screenshot(pixel_ratio=1, delay=400), 20)
                assert data.startswith(b"\x89PNG\r\n\x1a\n"), "Captura nativa inválida"
                path = OUTPUT / f"{viewport}-{name}.png"
                path.write_bytes(data)
                captures.append({"file": path.name, "width": page.width, "height": page.height})
                print(f"Captura: {path.name} ({page.width} x {page.height})", flush=True)

            if app:
                await app.close()
                page.services.clear()
            # El formulario de acceso real se presenta sin enviar credenciales.
            app = MunicipalApp(page, Settings(mode="supabase"), DemoRepository())
            app.login()
            await capture("01-login")
            AccountScreen(app).public_form("recovery")
            await capture("02-recovery")
            app.settings = Settings()
            app.profile = await app.repo.sign_in()
            app.departments = await app.repo.departments()
            app.shell()
            await app.navigate(0)
            await capture("03-dashboard")
            await app.navigate(1)
            await app.content.scroll_to(offset=0)
            await capture("04-inbox")
            app.filters = {"priority": "alta"}
            await app.navigate(1)
            await capture("05-filters")
            app.filters = {}
            await app.new_handler(None)
            await app.content.scroll_to(offset=0)
            await capture("06-register")
            case = (await app.repo.list_cases())[0]
            await app.detail(case["id"], reset_scroll=True)
            await capture("07-detail")
            await app.navigate(2)
            await app.content.scroll_to(offset=0)
            await capture("08-catalog")
            await app.navigate(3)
            await app.content.scroll_to(offset=0)
            await capture("09-admin")
            await show_report(app)
            await app.content.scroll_to(offset=0)
            await capture("10-report")
        (OUTPUT / "result.json").write_text(
            json.dumps({"ok": True, "data": "DemoRepository", "captures": captures}, indent=2),
            encoding="utf-8",
        )
    except Exception:
        failure = traceback.format_exc()
        print(failure, flush=True)
        (OUTPUT / "failure.txt").write_text(failure, encoding="utf-8")
    finally:
        if app:
            await app.close()
        await page.window.destroy()


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ft.run(main)
    if failure or len(captures) != 20:
        raise SystemExit(failure or "No se completaron las veinte capturas nativas.")
