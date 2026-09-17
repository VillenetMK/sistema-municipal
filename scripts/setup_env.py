"""Crea la configuración local municipal sin sobrescribir un archivo existente."""

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    try:
        content = (root / ".env.example").read_text(encoding="utf-8")
        with target.open("x", encoding="utf-8", newline="\n") as env_file:
            env_file.write(content)
    except FileExistsError:
        print(f"Ya existe {target}. Se conserva sin cambios.")
        return 0
    except OSError as error:
        print(f"No se pudo crear .env: {error}", file=sys.stderr)
        return 1

    print(f"Creado {target}")
    print("La aplicación leerá esta configuración al volver a iniciarse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
