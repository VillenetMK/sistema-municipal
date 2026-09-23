import json
from copy import deepcopy

import pytest

from scripts.municipal_backup import (
    PROJECT,
    ROOT,
    TABLES,
    BackupError,
    canonical,
    collect_members,
    decrypt_members,
    digest,
    encrypt_members,
    restore_sql,
    validate_snapshot,
)


def snapshot_fixture():
    tables = {name: [] for name in TABLES}
    tables["public.municipal_settings"] = [
        {"id": 1, "institution_name": "Municipalidad Provincial de Chiclayo"}
    ]
    content = b"%PDF-1.7\nDocumento ficticio para ensayo local.\n"
    tables["public.case_documents"] = [
        {"object_path": "case/document.pdf", "sha256": digest(content), "size_bytes": len(content)}
    ]
    return {
        "format": 1,
        "project_ref": PROJECT,
        "created_at": "2026-09-23T00:00:00Z",
        "tables": tables,
        "app_tables": [n for n in TABLES if not n.startswith("auth.")],
        "unsupported_auth": 0,
        "columns": [
            {"table": t, "name": "id", "type": "uuid"} for t in ("auth.users", "auth.identities")
        ],
        "storage_objects": [{"name": "case/document.pdf"}],
        "migrations": [
            p.stem.split("_", 1)[1] for p in (ROOT / "supabase/migrations").glob("*.sql")
        ],
    }, content


def test_backup_encrypts_and_restores_every_member_and_rejects_tampering():
    snapshot, content = snapshot_fixture()
    members = collect_members(snapshot, lambda _: content)
    encrypted = encrypt_members(members, "private-passphrase-for-tests")
    assert content not in encrypted and b"Municipalidad Provincial" not in encrypted
    assert decrypt_members(encrypted, "private-passphrase-for-tests") == members
    for data, password in [
        (encrypted[:-1] + bytes([encrypted[-1] ^ 1]), "private-passphrase-for-tests"),
        (encrypted, "wrong-passphrase"),
    ]:
        with pytest.raises(BackupError, match="incorrecta|alterado"):
            decrypt_members(data, password)


def test_missing_or_damaged_document_blocks_backup():
    snapshot, content = snapshot_fixture()
    with pytest.raises(BackupError, match="huella"):
        collect_members(snapshot, lambda _: b"corrupted")
    snapshot["storage_objects"] = []
    with pytest.raises(BackupError, match="Falta un archivo"):
        collect_members(snapshot, lambda _: content)


@pytest.mark.parametrize(
    "change",
    [
        {"project_ref": "kslzmrddrhfyyrxyfmbw"},
        {"unsupported_auth": 1},
        {"app_tables": []},
        {"storage_objects": [{"name": "../escape"}]},
    ],
)
def test_incompatible_source_or_unsafe_file_paths_fail_closed(change):
    snapshot, _ = snapshot_fixture()
    snapshot.update(change)
    with pytest.raises(BackupError):
        validate_snapshot(snapshot)


def test_restore_requires_empty_local_database_and_known_migrations():
    snapshot, content = snapshot_fixture()
    members = collect_members(snapshot, lambda _: content)
    sql = restore_sql(members)
    assert "current_database() <> 'munigest_restore'" in sql
    assert "El destino debe estar vacío" in sql
    assert "except all" in sql
    assert "enable trigger user" in sql
    changed = deepcopy(members)
    migration = next(name for name in changed if name.startswith("migrations/"))
    changed[migration] += b"\n-- unknown code"
    with pytest.raises(BackupError, match="migración"):
        restore_sql(changed)


def test_valid_manifest_cannot_hide_missing_document():
    snapshot, content = snapshot_fixture()
    members = collect_members(snapshot, lambda _: content)
    manifest = json.loads(members["manifest.json"])
    del members["objects/case/document.pdf"]
    del manifest["files"]["objects/case/document.pdf"]
    members["manifest.json"] = canonical(manifest)
    encrypted = encrypt_members(members, "private-passphrase-for-tests")
    with pytest.raises(BackupError, match="documentos"):
        decrypt_members(encrypted, "private-passphrase-for-tests")


def test_archived_migration_accepts_timestamp_alignment_only_with_identical_content():
    snapshot, content = snapshot_fixture()
    members = collect_members(snapshot, lambda _: content)
    original = next(n for n in members if n.endswith("_municipal_accounts.sql"))
    archived = "migrations/20260923132741_municipal_accounts.sql"
    members[archived] = members.pop(original)
    assert "accept_staff_invitation" in restore_sql(members)
    members[archived] += b"\n-- changed"
    with pytest.raises(BackupError, match="migración"):
        restore_sql(members)
