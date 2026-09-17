import asyncio
import json
import time
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import flet as ft
import httpx
import pytest
from test_administration import walk
from test_domain import draft
from test_ui import PageStub, assert_valid_wrapping_layout

from munigest.config import Settings
from munigest.demo import DemoRepository
from munigest.domain import UserError, export_cases, municipal_today, validate_draft
from munigest.repository import SupabaseRepository
from munigest.ui import MunicipalApp
from munigest.work_queue import due_notice, matches_filters, rest_filters, validate_filters


@pytest.mark.parametrize(
    "change",
    [
        {"department_id": "x),status.eq.archivado"},
        {"assignee": "admin"},
        {"received_from": "2026-02-30"},
        {"received_from": "2026-10-02", "received_to": "2026-10-01"},
        {"pending_only": "false"},
        {"due": "legal"},
        {"priority": "superior"},
    ],
)
def test_invalid_filters_are_rejected_before_request(change):
    with pytest.raises(UserError):
        validate_filters(change)


@pytest.mark.parametrize(
    "timestamp,expected",
    [
        ("2026-09-17T04:59:59Z", False),
        ("2026-09-17T05:00:00Z", True),
        ("2026-09-18T04:59:59Z", True),
        ("2026-09-18T05:00:00Z", False),
    ],
)
def test_received_dates_cover_complete_chiclayo_day(timestamp, expected):
    item = {"status": "recibido", "created_at": timestamp}
    filters = {"received_from": "2026-09-17", "received_to": "2026-09-17"}
    assert matches_filters(item, filters, None) is expected
    condition = rest_filters(filters, None)["and"]
    assert "created_at.gte.2026-09-17T00:00:00-05:00" in condition
    assert "created_at.lt.2026-09-18T00:00:00-05:00" in condition


def test_due_notices_and_filters_agree_and_ignore_closed_cases():
    today = date(2026, 9, 17)
    for days, label, filter_name in [
        (-1, "Objetivo vencido", "overdue"),
        (0, "Objetivo hoy", "today"),
        (1, "Objetivo en próximos 3 días", "soon"),
        (3, "Objetivo en próximos 3 días", "soon"),
    ]:
        item = {
            "status": "recibido",
            "created_at": "2026-09-17T10:00:00Z",
            "due_on": str(today + timedelta(days=days)),
        }
        assert due_notice(item, today) == label
        assert matches_filters(item, {"due": filter_name}, None, today)
        assert not matches_filters(item | {"status": "atendido"}, {"due": filter_name}, None, today)
        assert due_notice(item | {"status": "archivado"}, today) == ""
    assert due_notice(item | {"due_on": "2026-09-21"}, today) == ""
    assert not matches_filters(item | {"due_on": "2026-09-21"}, {"due": "soon"}, None, today)


@pytest.mark.parametrize("field", ["procedure_id", "assigned_to"])
def test_registration_checks_work_identifiers(field):
    with pytest.raises(UserError):
        validate_draft(draft(**{field: "invalid"}))


def test_rest_filters_and_fk_hint_are_sent_before_pagination():
    user_id, department_id, procedure_id = str(uuid4()), str(uuid4()), str(uuid4())
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=[])

    async def exercise():
        repo = SupabaseRepository(
            Settings(
                mode="supabase",
                url="https://lxvmwjcqdjoidgpinmgm.supabase.co",
                key="sb_publishable_test",
            ),
            httpx.MockTransport(handler),
        )
        repo.profile = {"user_id": user_id}
        repo.session = {
            "access_token": "test-access",
            "refresh_token": "r",
            "expires_at": time.time() + 3600,
        }
        try:
            await repo.list_cases(
                "solicitud",
                "en_revision",
                50,
                filters={
                    "assignee": "mine",
                    "pending_only": True,
                    "department_id": department_id,
                    "procedure_id": procedure_id,
                    "priority": "alta",
                    "due": "today",
                },
            )
            params = calls[0].url.params
            assert params["offset"] == "50" and params["limit"] == "51"
            assert params["status"] == "eq.en_revision"
            assert f"assigned_to.eq.{user_id}" in params["and"]
            assert f"department_id.eq.{department_id}" in params["and"]
            assert f"procedure_id.eq.{procedure_id}" in params["and"]
            assert (
                "priority.eq.alta" in params["and"]
                and "status.not.in.(atendido,archivado)" in params["and"]
            )
            assert "!cases_assigned_to_fkey" in params["select"]
            await repo.set_case_work(
                {"id": str(uuid4()), "version": 3},
                {
                    "procedure_id": procedure_id,
                    "assigned_to": user_id,
                    "priority": "alta",
                    "due_on": None,
                    "note": "Organización autorizada del expediente.",
                },
            )
            assert calls[1].url.path == "/rest/v1/rpc/set_case_work"
            assert json.loads(calls[1].content)["expected_version"] == 3
            assert json.loads(calls[1].content)["assigned_to"] == user_id
        finally:
            await repo.close()

    asyncio.run(exercise())


def test_demo_filters_paginate_after_filtering_and_keep_fiche_history():
    async def exercise():
        repo = DemoRepository(False)
        profile = await repo.sign_in()
        procedure = (await repo.procedures())[0]
        target = await repo.create_case(
            draft(assigned_to=profile["user_id"], procedure_id=procedure["id"])
        )
        for i in range(52):
            await repo.create_case(draft(title=f"Solicitud sin responsable {i}"))
        assert len(await repo.list_cases(filters={"assignee": "mine"})) == 1
        assert len(await repo.list_cases(filters={"assignee": "unassigned"})) == 51
        assert len(await repo.list_cases(offset=50, filters={"assignee": "unassigned"})) == 2
        await repo.admin_save(
            "procedures",
            procedure | {"name": "Nuevo nombre del catálogo", "is_active": False},
            1,
            "Cambio de catálogo para comprobar conservación.",
        )
        unchanged = await repo.get_case(target["id"])
        assert unchanged["procedure_snapshot"]["name"] == "Solicitud general"
        changed = await repo.set_case_work(
            target,
            {
                "procedure_id": procedure["id"],
                "assigned_to": profile["user_id"],
                "priority": "urgente",
                "due_on": str(municipal_today()),
                "note": "Priorizar solicitud con fecha objetivo interna.",
            },
        )
        assert changed["procedure_snapshot"] == unchanged["procedure_snapshot"]
        with pytest.raises(UserError, match="Otro usuario"):
            await repo.set_case_work(
                target,
                {
                    "procedure_id": procedure["id"],
                    "priority": "normal",
                    "assigned_to": None,
                    "note": "Cambio desde una pantalla antigua.",
                },
            )
        assert len(await repo.list_cases(filters={"due": "today"})) == 1
        csv = export_cases([changed]).decode("utf-8-sig")
        assert "Trámite,Responsable" in csv and profile["display_name"] in csv
        assert "01234567" not in csv
        await repo.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("width", [390, 1280])
def test_ui_register_assign_organize_transfer_and_use_quick_filters(width):
    async def exercise():
        page = PageStub()
        page.width = width
        repo = DemoRepository(False)
        app = MunicipalApp(page, Settings(), repo)
        app.profile = await repo.sign_in()
        app.departments = await repo.departments()
        repo._procedures[0]["department_id"] = app.profile["department_id"]
        app.shell()

        def field(label):
            return next(
                c
                for c in walk(app.content)
                if isinstance(c, (ft.TextField, ft.Dropdown, ft.Checkbox)) and c.label == label
            )

        async def click(text):
            button = next(
                c
                for c in walk(app.content)
                if isinstance(c, (ft.FilledButton, ft.OutlinedButton, ft.TextButton))
                and c.content == text
            )
            await button.on_click(SimpleNamespace(control=button))
            assert_valid_wrapping_layout(app.content)

        await app.new_handler(None)
        assert field("Área de destino").value == app.profile["department_id"]
        assert app.profile["user_id"] in [o.key for o in field("Responsable (opcional)").options]
        field("Responsable (opcional)").value = app.profile["user_id"]
        for label, value in {
            "Número de documento": "00000001",
            "Nombre completo o razón social": "Solicitante de prueba",
            "Asunto": "Solicitud desde formulario",
            "Descripción de la solicitud": "Descripción suficiente para la prueba de registro.",
        }.items():
            field(label).value = value
        await click("Guardar y generar expediente")
        item = (await repo.list_cases())[0]
        assert item["assigned_to"] == app.profile["user_id"] and item["procedure_id"]
        field("Prioridad").value = "urgente"
        field("Fecha objetivo interna").value = str(municipal_today())
        field("Motivo de la organización").value = "Dar prioridad a la solicitud para atención hoy."
        await click("Guardar organización")
        assert (await repo.get_case(item["id"]))["version"] == 2
        await app.navigate(1)
        await click("Mis pendientes")
        assert len(app.rows) == 1
        await click("Objetivo hoy")
        assert len(app.rows) == 1
        await app.detail(item["id"])
        other = next(d for d in app.departments if d["id"] != item["department_id"])
        field("Área de destino").value = other["id"]
        field(
            "Motivo, observación o respuesta"
        ).value = "Derivar a otra área para continuar la atención."
        await click("Guardar actuación")
        changed = await repo.get_case(item["id"])
        assert changed["assigned_to"] is None
        assert (await repo.events(item["id"]))[0]["work_before"]["assignee_name"] == app.profile[
            "display_name"
        ]
        await app.navigate(1)
        await click("Mis pendientes")
        assert not app.rows
        await click("Sin responsable")
        assert len(app.rows) == 1
        app.profile["role"] = "consulta"
        await app.detail(item["id"])
        assert not any(
            getattr(c, "content", None) == "Guardar organización" for c in walk(app.content)
        )
        await app.close()

    asyncio.run(exercise())
