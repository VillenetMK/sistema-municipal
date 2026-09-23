"""Contrato de respaldo para CI y PostgreSQL local; solo bases de nombre fijo."""

import json
import subprocess
import tempfile
from pathlib import Path

from scripts.municipal_backup import (
    ROOT,
    SNAPSHOT_QUERY,
    collect_members,
    decrypt_members,
    encrypt_members,
    restore_sql,
)


def psql(database, sql):
    if database not in {"municipal_test", "munigest_restore"}:
        raise ValueError("Solo destinos de prueba locales")
    result = subprocess.run(
        [
            "psql",
            "-X",
            "-A",
            "-t",
            "-q",
            "-h",
            "127.0.0.1",
            "-U",
            "postgres",
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Falló PostgreSQL local en el contrato de restauración")
    return result.stdout


def main():
    psql("municipal_test", (ROOT / "tests/backup_fixture.sql").read_text())
    migrations = sorted((ROOT / "supabase/migrations").glob("*.sql"))
    psql(
        "municipal_test",
        "insert into supabase_migrations.schema_migrations values "
        + ",".join(f"('{p.stem.split('_', 1)[0]}','{p.stem.split('_', 1)[1]}')" for p in migrations)
        + ";",
    )
    snapshot = json.loads(psql("municipal_test", SNAPSHOT_QUERY))
    content = b"%PDF-1.7\nAdjunto ficticio del ensayo de respaldo.\n"
    members = collect_members(snapshot, lambda _: content)
    encrypted = encrypt_members(members, "local-test-passphrase-only")
    recovered = decrypt_members(encrypted, "local-test-passphrase-only")
    psql("munigest_restore", restore_sql(recovered))
    with tempfile.TemporaryDirectory() as directory:
        for name, data in recovered.items():
            if name.startswith("objects/"):
                path = Path(directory) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                assert path.read_bytes() == content
    assert psql("munigest_restore", "select count(*) from public.cases;").strip() == "1"
    assert psql("munigest_restore", "select count(*) from public.case_documents;").strip() == "1"
    try:
        psql("munigest_restore", restore_sql(recovered))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Se permitió restaurar sobre una base existente")
    print("Respaldo cifrado, expediente, historial, adjunto y rechazo de sobrescritura: OK")


if __name__ == "__main__":
    main()
