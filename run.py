"""Ejecutar desde la raíz: python run.py --web o python run.py."""

import argparse
import os
import sys
from pathlib import Path

import flet as ft

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from munigest.config import Settings  # noqa: E402
from munigest.ui import main  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MuniGest")
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8550")))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("El puerto debe estar entre 1 y 65535.")
    # Detener el servidor si la configuración es inválida antes de aceptar sesiones.
    try:
        Settings.from_env()
    except ValueError as exc:
        parser.error(str(exc))
    ft.run(
        main,
        view=ft.AppView.WEB_BROWSER if args.web else ft.AppView.FLET_APP,
        host=args.host,
        port=args.port,
        no_cdn=True,
    )
