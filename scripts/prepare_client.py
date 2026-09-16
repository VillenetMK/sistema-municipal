"""Incluye solo configuración pública en un ejecutable nativo."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from munigest.config import Settings  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["demo", "supabase"], required=True)
args = parser.parse_args()
settings = Settings.from_env()
settings = Settings(
    mode=args.mode,
    name=settings.name,
    project_ref=settings.project_ref,
    url=settings.url,
    key=settings.key,
)
settings.validate()
data = {
    "MUNIGEST_MODE": settings.mode,
    "MUNIGEST_NAME": settings.name,
    "SUPABASE_PROJECT_REF": settings.project_ref,
    "SUPABASE_URL": settings.url,
    "SUPABASE_PUBLISHABLE_KEY": settings.key if settings.mode == "supabase" else "",
}
target = ROOT / "src/munigest/_build_settings.py"
target.write_text(
    "# Generado para empaquetado. Nunca contiene claves secretas.\nCONFIG = " + repr(data) + "\n",
    encoding="utf-8",
)
print(f"Configuración {settings.mode} preparada; no se mostraron claves.")
