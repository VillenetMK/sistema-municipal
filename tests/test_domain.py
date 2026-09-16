import asyncio
from datetime import date
from uuid import uuid4

import pytest

from munigest.config import Settings
from munigest.demo import DEPARTMENTS, DemoRepository
from munigest.domain import (
    UserError,
    export_cases,
    overdue,
    safe_csv_cell,
    validate_attachment,
    validate_draft,
    validate_transition,
)


def draft(**overrides):
    return {
        "request_id": str(uuid4()),
        "document_type": "DNI",
        "document_number": "01234567",
        "applicant_name": "Solicitante de prueba",
        "email": "",
        "phone": "",
        "title": "Solicitud de revisión",
        "description": "Descripción completa para revisar una solicitud.",
        "department_id": DEPARTMENTS[0]["id"],
        "priority": "normal",
        "channel": "presencial",
        "due_on": None,
        **overrides,
    }


@pytest.mark.parametrize(
    "change",
    [
        {"document_number": "123"},
        {"document_number": "１２３４５６７８"},
        {"document_type": "RUC", "document_number": "12345678"},
        {"email": "dato@invalido"},
        {"phone": "9" * 40},
        {"department_id": "otro"},
        {"title": ""},
        {"description": "corto"},
        {"due_on": "2026-02-30"},
        {"priority": "admin"},
        {"channel": "externo"},
    ],
)
def test_invalid_requests_rejected(change):
    with pytest.raises(UserError):
        validate_draft(draft(**change))


def test_leading_zero_in_dni_preserved():
    assert validate_draft(draft())["document_number"] == "01234567"


def test_cannot_jump_from_received_to_archived():
    with pytest.raises(UserError):
        validate_transition("recibido", "archivado", "Motivo suficientemente largo")


def test_transfer_requires_actual_change():
    with pytest.raises(UserError):
        validate_transition("recibido", "recibido", "Motivo suficientemente largo")
    assert validate_transition("recibido", "recibido", "Derivación a otra unidad", False)


def test_attachment_checks_content_and_size():
    with pytest.raises(UserError):
        validate_attachment("archivo.pdf", b"not-a-pdf")
    with pytest.raises(UserError):
        validate_attachment("archivo.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024))
    assert validate_attachment("../solicitud.pdf", b"%PDF-1.7\n")[0] == "solicitud.pdf"


@pytest.mark.parametrize("value", ["=HYPERLINK(1)", "+cmd", "-1+2", "@SUM(A1)", "  =cmd", "\tcmd"])
def test_csv_formula_injection_blocked(value):
    assert safe_csv_cell(value).startswith("'")


def test_internal_deadline_respects_terminal_states():
    today = date(2026, 9, 16)
    assert overdue({"status": "en_revision", "due_on": "2026-09-15"}, today)
    assert not overdue({"status": "atendido", "due_on": "2026-09-15"}, today)


def test_demo_session_isolation_and_transaction_contract():
    async def exercise():
        first, other = DemoRepository(False), DemoRepository(False)
        await first.sign_in()
        request = draft()
        case = await first.create_case(request)
        again = await first.create_case(request)
        assert case["id"] == again["id"]
        assert (await first.metrics())["total"] == 1
        assert (await other.metrics())["total"] == 0
        changed = await first.advance_case(
            case, "en_revision", case["department_id"], "Inicio de la revisión interna."
        )
        assert changed["version"] == 2
        with pytest.raises(UserError):
            await first.advance_case(
                case, "observado", case["department_id"], "Intento desde una versión anterior."
            )
        assert len(await first.events(case["id"])) == 2
        assert b"01234567" not in export_cases(await first.list_cases())

    asyncio.run(exercise())


def test_other_project_and_secret_keys_rejected():
    with pytest.raises(ValueError):
        Settings(
            mode="supabase",
            url="https://kslzmrddrhfyyrxyfmbw.supabase.co",
            key="sb_publishable_test",
        ).validate()
    with pytest.raises(ValueError):
        Settings(
            mode="supabase",
            url="https://lxvmwjcqdjoidgpinmgm.supabase.co",
            key="sb_secret_forbidden",
        ).validate()
    with pytest.raises(ValueError):
        Settings(
            mode="supabase",
            project_ref="kslzmrddrhfyyrxyfmbw",
            url="https://kslzmrddrhfyyrxyfmbw.supabase.co",
            key="sb_publishable_test",
        ).validate()


def test_live_mode_never_falls_back_to_demo():
    with pytest.raises(ValueError):
        Settings(mode="supabase").validate()
