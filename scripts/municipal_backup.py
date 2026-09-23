"""Respaldo cifrado del piloto y ensayo de restauración exclusivamente local.

Operador de confianza: secretos por prompt oculto, nunca desde el cliente Flet.
No reemplaza un backup físico completo de Supabase ni restaura servicios hospedados.
"""

import argparse
import getpass
import hashlib
import io
import json
import os
import re
import secrets
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "lxvmwjcqdjoidgpinmgm"
URL = f"https://{PROJECT}.supabase.co"
TABLES = (
    "auth.users",
    "auth.identities",
    "public.municipal_settings",
    "public.departments",
    "public.staff_profiles",
    "public.procedures",
    "public.applicants",
    "public.cases",
    "public.case_events",
    "public.case_documents",
    "public.admin_events",
    "private.case_counters",
    "private.staff_invitations",
)
MAGIC = b"MUNIGEST-BACKUP-1\n"
MAX_BYTES = 512 * 1024 * 1024
TABLE_VALUES = ",".join("'" + name + "'" for name in TABLES)
SNAPSHOT_QUERY = (
    "select jsonb_build_object("
    + ",".join(
        [
            "'format',1",
            f"'project_ref','{PROJECT}'",
            "'created_at',now()",
            "'tables',jsonb_build_object("
            + ",".join(
                f"'{table}',(select coalesce(jsonb_agg(to_jsonb(r)),'[]') from {table} r)"
                for table in TABLES
            )
            + ")",
            "'columns',(select jsonb_agg(jsonb_build_object('table',table_schema||'.'||table_name,'name',column_name,'type',data_type) order by table_schema,table_name,ordinal_position) from information_schema.columns where table_schema||'.'||table_name in ("
            + TABLE_VALUES
            + "))",
            "'app_tables',(select jsonb_agg(schemaname||'.'||tablename order by schemaname,tablename) from pg_tables where schemaname in ('public','private'))",
            "'unsupported_auth',(select count(*) from auth.mfa_factors)+(select count(*) from auth.identities where provider<>'email')+(select count(*) from auth.users where phone is not null and phone<>'')",
            "'storage_objects',(select coalesce(jsonb_agg(jsonb_build_object('name',name) order by name),'[]') from storage.objects where bucket_id='expedientes')",
            "'migrations',(select jsonb_agg(name order by version) from supabase_migrations.schema_migrations)",
        ]
    )
    + ") as snapshot;"
)


class BackupError(Exception):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_path(value):
    p = PurePosixPath(value)
    if (
        not value
        or p.is_absolute()
        or any(part in {".", ".."} for part in value.split("/"))
        or "\\" in value
        or ":" in value
        or "\x00" in value
    ):
        raise BackupError("Ruta de archivo inválida en el respaldo.")
    return p


def validate_snapshot(snapshot):
    if snapshot.get("format") != 1 or snapshot.get("project_ref") != PROJECT:
        raise BackupError("El respaldo no pertenece al proyecto municipal compatible.")
    if set(snapshot.get("tables", {})) != set(TABLES):
        raise BackupError("Faltan tablas del respaldo.")
    if set(snapshot.get("app_tables", [])) != {t for t in TABLES if not t.startswith("auth.")}:
        raise BackupError("El esquema cambió. Actualiza el respaldo antes de continuar.")
    if snapshot.get("unsupported_auth") != 0:
        raise BackupError(
            "Hay MFA, teléfono o proveedores externos. Usa un respaldo completo de Supabase para conservarlos."
        )
    settings = snapshot["tables"]["public.municipal_settings"]
    if (
        len(settings) != 1
        or settings[0].get("institution_name") != "Municipalidad Provincial de Chiclayo"
    ):
        raise BackupError("La identidad institucional no coincide.")
    for name in TABLES:
        if not isinstance(snapshot["tables"][name], list):
            raise BackupError("Tabla incompleta en el respaldo.")
    names = [item["name"] for item in snapshot["storage_objects"]]
    if len(names) != len(set(names)):
        raise BackupError("Inventario de documentos duplicado.")
    for name in names:
        checked_path(name)
    for doc in snapshot["tables"]["public.case_documents"]:
        if doc["object_path"] not in names:
            raise BackupError("Falta un archivo adjunto en Storage. Respaldo cancelado.")


def source_snapshot(token):
    # Una sola sentencia SQL produce una fotografía consistente de todas las tablas.
    with httpx.Client(timeout=120, follow_redirects=False) as client:
        response = client.post(
            f"https://api.supabase.com/v1/projects/{PROJECT}/database/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": SNAPSHOT_QUERY, "read_only": True},
        )
        if response.status_code != 200:
            raise BackupError(f"No se pudo leer la base municipal (HTTP {response.status_code}).")
        snapshot = response.json()[0]["snapshot"]
    validate_snapshot(snapshot)
    return snapshot


def collect_members(snapshot, download, root=ROOT):
    validate_snapshot(snapshot)
    migrations = sorted((root / "supabase/migrations").glob("*.sql"))
    expected = {p.stem.split("_", 1)[1] for p in migrations}
    if expected != set(snapshot["migrations"] or []):
        raise BackupError("Las migraciones del repositorio y de la base no coinciden.")
    members = {"snapshot.json": canonical(snapshot)}
    members.update({f"migrations/{p.name}": p.read_bytes() for p in migrations})
    documents = {d["object_path"]: d for d in snapshot["tables"]["public.case_documents"]}
    total = sum(map(len, members.values()))
    for item in snapshot["storage_objects"]:
        path = item["name"]
        content = download(path)
        doc = documents.get(path)
        if doc and (digest(content) != doc["sha256"] or len(content) != doc["size_bytes"]):
            raise BackupError("Un adjunto no coincide con su huella o tamaño. Respaldo cancelado.")
        total += len(content)
        if total > MAX_BYTES:
            raise BackupError(
                "Este respaldo supera 512 MiB. Usa un respaldo completo por streaming."
            )
        members[f"objects/{path}"] = content
    manifest = {
        "format": 1,
        "project_ref": PROJECT,
        "created_at": snapshot["created_at"],
        "counts": {t: len(rows) for t, rows in snapshot["tables"].items()},
        "files": {
            name: {"size": len(data), "sha256": digest(data)} for name, data in members.items()
        },
        "coverage": "Tablas municipales, cuentas email/password, migraciones y objetos de expedientes. Sin sesiones, SMTP, API keys, configuración de plataforma ni funciones Edge.",
    }
    members["manifest.json"] = canonical(manifest)
    return members


def encrypt_members(members, passphrase):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    if len(passphrase) < 16:
        raise BackupError("Usa una frase de respaldo de al menos 16 caracteres.")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            checked_path(name)
            archive.writestr(name, data)
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode())
    return MAGIC + salt + nonce + AESGCM(key).encrypt(nonce, stream.getvalue(), MAGIC)


def decrypt_members(data, passphrase):
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    if not data.startswith(MAGIC) or len(data) > MAX_BYTES + 1024 * 1024:
        raise BackupError("Archivo de respaldo inválido o demasiado grande.")
    offset = len(MAGIC)
    salt, nonce = data[offset : offset + 16], data[offset + 16 : offset + 28]
    key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode())
    try:
        clear = AESGCM(key).decrypt(nonce, data[offset + 28 :], MAGIC)
    except (InvalidTag, ValueError):
        raise BackupError("Frase incorrecta o respaldo alterado. No se restauró nada.") from None
    with zipfile.ZipFile(io.BytesIO(clear)) as archive:
        infos = archive.infolist()
        if sum(i.file_size for i in infos) > MAX_BYTES or len({i.filename for i in infos}) != len(
            infos
        ):
            raise BackupError("Archivo de respaldo inválido.")
        for info in infos:
            checked_path(info.filename)
        members = {i.filename: archive.read(i) for i in infos}
    manifest = json.loads(members["manifest.json"])
    if manifest.get("project_ref") != PROJECT or set(manifest["files"]) != set(members) - {
        "manifest.json"
    }:
        raise BackupError("Inventario incompleto.")
    for name, expected in manifest["files"].items():
        if len(members[name]) != expected["size"] or digest(members[name]) != expected["sha256"]:
            raise BackupError("Falló la comprobación de integridad.")
    snapshot = json.loads(members["snapshot.json"])
    validate_snapshot(snapshot)
    if {t: len(rows) for t, rows in snapshot["tables"].items()} != manifest["counts"]:
        raise BackupError("Conteos inconsistentes.")
    expected_objects = {f"objects/{o['name']}" for o in snapshot["storage_objects"]}
    if {name for name in members if name.startswith("objects/")} != expected_objects:
        raise BackupError("Faltan documentos del inventario.")
    for doc in snapshot["tables"]["public.case_documents"]:
        content = members[f"objects/{doc['object_path']}"]
        if digest(content) != doc["sha256"] or len(content) != doc["size_bytes"]:
            raise BackupError("Adjunto alterado.")
    return members


def sql_literal(value):
    return "'" + value.replace("'", "''") + "'"


def restore_sql(members, root=ROOT):
    """Ensayo con tablas Auth mínimas; no es un servidor Supabase restaurado."""
    snapshot = json.loads(members["snapshot.json"])
    validate_snapshot(snapshot)
    statements = [
        "begin; set local standard_conforming_strings=on;",
        """
    do $$ begin
      if current_database() <> 'munigest_restore' then raise exception 'Solo munigest_restore'; end if;
      if exists(select 1 from pg_tables where schemaname in ('public','private','auth','storage')) then
        raise exception 'El destino debe estar vacío'; end if;
    end $$;
    """,
    ]
    bootstrap = (root / "tests/bootstrap_database.sql").read_text()
    # No recrear roles globales existentes en el servidor local.
    bootstrap = bootstrap.replace(
        "create role anon nologin;",
        "do $$ begin if not exists(select 1 from pg_roles where rolname='anon') then create role anon nologin; end if; end $$;",
    )
    bootstrap = bootstrap.replace(
        "create role authenticated nologin;",
        "do $$ begin if not exists(select 1 from pg_roles where rolname='authenticated') then create role authenticated nologin; end if; end $$;",
    )
    auth_ddl = []
    allowed_types = {
        "uuid",
        "text",
        "character varying",
        "timestamp with time zone",
        "jsonb",
        "boolean",
        "smallint",
    }
    for table in ("auth.users", "auth.identities"):
        cols = []
        for column in snapshot["columns"]:
            if column["table"] != table:
                continue
            if (
                not re.fullmatch(r"[a-z_][a-z_0-9]*", column["name"])
                or column["type"] not in allowed_types
            ):
                raise BackupError("El esquema Auth cambió. Revisa el ensayo antes de continuar.")
            cols.append(
                f'"{column["name"]}" {column["type"]}'
                + (" primary key" if column["name"] == "id" else "")
            )
        if not cols:
            raise BackupError("Falta el esquema Auth.")
        auth_ddl.append(f"create table {table} ({','.join(cols)});")
    bootstrap = bootstrap.replace(
        "create table auth.users(id uuid primary key,email text,raw_user_meta_data jsonb default '{}');",
        "\n".join(auth_ddl),
    )
    statements.append(bootstrap)
    for name in sorted(n for n in members if n.startswith("migrations/")):
        if not re.fullmatch(r"migrations/\d{14}_[a-z_0-9]+\.sql", name):
            raise BackupError("Nombre de migración inválido.")
        source = root / "supabase" / name
        if not source.is_file():
            # Supabase asigna el timestamp al aplicar por API. Una copia anterior
            # puede conservar el nombre generado por CLI; exigir nombre lógico y bytes idénticos.
            logical_name = Path(name).name.split("_", 1)[1]
            matches = list((root / "supabase/migrations").glob(f"*_{logical_name}"))
            if len(matches) == 1:
                source = matches[0]
        if not source.is_file() or source.read_bytes() != members[name]:
            raise BackupError(
                "Una migración no coincide con este repositorio. Usa la revisión del respaldo."
            )
        # Las migraciones se ejecutan dentro de la transacción única del ensayo.
        migration = members[name].decode()
        migration = re.sub(r"(?im)^\s*(begin|commit);\s*$", "", migration)
        statements.append(migration)
    for table in TABLES:
        statements.append(f"alter table {table} disable trigger user;")
    for table in reversed(TABLES):
        statements.append(f"delete from {table};")
    for table in TABLES:
        rows = snapshot["tables"][table]
        value = sql_literal(canonical(rows).decode())
        statements.append(
            f"insert into {table} overriding system value select * from jsonb_populate_recordset(null::{table},{value}::jsonb);"
        )
        # Comparación multiconjunto: detecta filas faltantes, alteradas y duplicadas.
        statements.append(
            f"do $verify$ begin if exists((select to_jsonb(t) from {table} t except all select to_jsonb(e) from jsonb_populate_recordset(null::{table},{value}::jsonb) e) union all (select to_jsonb(e) from jsonb_populate_recordset(null::{table},{value}::jsonb) e except all select to_jsonb(t) from {table} t)) then raise exception 'Diferencia al restaurar {table}'; end if; end $verify$;"
        )
    for table in ("public.case_events", "public.admin_events"):
        statements.append(
            f"select setval(pg_get_serial_sequence('{table}','id'), greatest(coalesce(max(id),0),1),count(*)>0) from {table};"
        )
    for table in TABLES:
        statements.append(f"alter table {table} enable trigger user;")
    statements.append("commit;")
    return "\n".join(statements)


def private_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("archive", type=Path)
    restore = sub.add_parser("restore-test")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--output-dir", type=Path, required=True)
    restore.add_argument("--port", type=int, default=5432)
    restore.add_argument("--db-user", default="postgres")
    args = parser.parse_args(argv)
    passphrase = getpass.getpass("Frase privada del respaldo (mínimo 16 caracteres): ")
    if args.command == "backup":
        if passphrase != getpass.getpass("Repite la frase: "):
            raise BackupError("Las frases no coinciden.")
        token = getpass.getpass("Token personal de Supabase (operador): ")
        snapshot = source_snapshot(token)
        key = (
            getpass.getpass("Clave administrativa del proyecto para descargar adjuntos: ")
            if snapshot["storage_objects"]
            else ""
        )
        with httpx.Client(
            base_url=URL, headers={"apikey": key}, timeout=60, follow_redirects=False
        ) as client:

            def download(path):
                response = client.get(
                    "/storage/v1/object/authenticated/expedientes/" + quote(path, safe="/")
                )
                if response.status_code != 200:
                    raise BackupError("No se pudo respaldar un adjunto. Archivo final no creado.")
                return response.content

            members = collect_members(snapshot, download)
        data = encrypt_members(members, passphrase)
        decrypt_members(data, passphrase)
        private_write(args.output, data)
        print(f"Respaldo cifrado y verificado: {args.output.name}. SHA-256: {digest(data)}")
        return
    members = decrypt_members(args.archive.read_bytes(), passphrase)
    manifest = json.loads(members["manifest.json"])
    if args.command == "verify":
        print(
            json.dumps(
                {
                    "project_ref": PROJECT,
                    "created_at": manifest["created_at"],
                    "counts": manifest["counts"],
                    "integrity": "OK",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if not 1024 <= args.port <= 65535 or args.db_user.startswith("-"):
        raise BackupError("Parámetros locales inválidos.")
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    sql = restore_sql(members)
    env = {
        **os.environ,
        "PGPASSWORD": getpass.getpass("Contraseña de PostgreSQL local: "),
        "PGCONNECT_TIMEOUT": "10",
    }
    # Host y base fijos: no se acepta una URL de producción ni EcoSphere.
    result = subprocess.run(
        [
            "psql",
            "-X",
            "-q",
            "-h",
            "127.0.0.1",
            "-p",
            str(args.port),
            "-U",
            args.db_user,
            "-d",
            "munigest_restore",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=sql.encode(),
        capture_output=True,
        env=env,
        check=False,
    )
    if result.returncode:
        # psql puede imprimir una fila sensible en un error; no mostrar stderr sin filtrar.
        raise BackupError(
            "Falló el ensayo local. Usa una base vacía llamada munigest_restore y PostgreSQL 17. La transacción no se confirmó."
        )
    for name, data in members.items():
        if name.startswith("objects/"):
            private_write(args.output_dir / checked_path(name), data)
    report = {
        "verified_at": datetime.now(UTC).isoformat(),
        "source_created_at": manifest["created_at"],
        "source_project": PROJECT,
        "rows": manifest["counts"],
        "objects": len([n for n in members if n.startswith("objects/")]),
        "database": "munigest_restore",
        "result": "Filas comparadas y documentos verificados",
        "scope": "Ensayo PostgreSQL; no inicia Auth ni Storage de Supabase.",
    }
    private_write(args.output_dir / "Restauracion_verificada.json", canonical(report))
    print(
        "Ensayo completado: filas comparadas y documentos restaurados. El proyecto hospedado no se modificó."
    )


if __name__ == "__main__":
    try:
        main()
    except (BackupError, OSError, httpx.HTTPError, ValueError, KeyError) as exc:
        print(
            str(exc)
            if isinstance(exc, BackupError)
            else "Operación incompleta. Revisa archivos, conexión y permisos; no se muestran datos privados.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
