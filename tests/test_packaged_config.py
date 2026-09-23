"""Regresión del arranque Android: los .py originales no existen dentro del APK."""

import os
import py_compile
import subprocess
import sys
from pathlib import Path

import pytest

from munigest import config


@pytest.mark.parametrize("with_env", [False, True])
def test_config_runs_from_bytecode_without_original_source(tmp_path, with_env):
    source = tmp_path / "src" / "munigest" / "config.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        Path(config.__file__).read_text()
        + '\nif __name__ == "__main__":\n    print(Settings.from_env().name)\n'
    )
    bytecode = source.with_suffix(".pyc")
    py_compile.compile(str(source), cfile=str(bytecode), doraise=True)
    source.unlink()
    if with_env:
        (tmp_path / ".env").write_text("MUNIGEST_NAME=Nombre del archivo\n")
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(config.__file__).resolve().parents[1]),
        "MUNIGEST_MODE": "demo",
        # El entorno debe conservar prioridad, aunque el archivo local exista.
        "MUNIGEST_NAME": "Cliente compilado",
    }
    result = subprocess.run(
        [sys.executable, str(bytecode)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Cliente compilado"
