"""Empaqueta el cliente Python para Pages, incluyendo solo archivos permitidos."""

import argparse
import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["supabase", "demo"], default="supabase")
    parser.add_argument("--output", default="dist/sistema-municipal")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    env = {
        **{k: v for k, v in dotenv_values(ROOT / ".env.example").items() if v is not None},
        **os.environ,
    }
    env["MUNIGEST_MODE"] = args.mode
    subprocess.run(
        [sys.executable, "scripts/prepare_client.py", "--mode", args.mode],
        cwd=ROOT,
        env=env,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "flet.cli",
            "publish",
            ".",
            "--distpath",
            str(output),
            "--python-version",
            "3.13",
            "--base-url",
            "/sistema-municipal/",
            "--route-url-strategy",
            "hash",
            "--app-name",
            "MuniGest Chiclayo",
            "--app-short-name",
            "MuniGest",
            "--app-description",
            "Mesa de partes y seguimiento de expedientes",
            "--pwa-theme-color",
            "#17665E",
            "--pwa-background-color",
            "#F3F6F6",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    archive = output / "app.tar.gz"
    clean = io.BytesIO()
    names = set()
    with (
        tarfile.open(archive, "r:gz") as source,
        tarfile.open(fileobj=clean, mode="w:gz") as target,
    ):
        for item in source.getmembers():
            name = item.name.lstrip("/")
            if not item.isfile() or not (
                name in {"main.py", "requirements.txt"}
                or (
                    name.startswith("munigest/")
                    and name.endswith(".py")
                    and "__pycache__" not in name
                )
            ):
                continue
            names.add(name)
            target.addfile(item, source.extractfile(item))
    assert {"main.py", "munigest/_build_settings.py", "requirements.txt"} <= names
    archive.write_bytes(clean.getvalue())
    (output / ".nojekyll").touch()
    print(
        f"Cliente {args.mode}: {len(names)} archivos Python y requisitos; sin .env ni herramientas administrativas."
    )


if __name__ == "__main__":
    main()
