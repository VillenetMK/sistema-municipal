import asyncio
import csv
import io
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import flet as ft
import httpx
import pytest
from pypdf import PdfReader
from test_administration import walk
from test_domain import draft
from test_repository import CONFIG
from test_ui import PageStub, assert_valid_wrapping_layout

from munigest.config import Settings
from munigest.demo import DemoRepository
from munigest.domain import UserError
from munigest.pdf_exports import receipt_pdf, summary_pdf
from munigest.report_ui import show_report
from munigest.reports import filter_description, local_timestamp, report_csv, report_summary
from munigest.repository import SupabaseRepository
from munigest.ui import MunicipalApp


def test_complete_csv_and_summary_use_all_matches_and_the_server_day():
    async def exercise():
        repo = DemoRepository(seeded=False)
        await repo.sign_in()
        for index in range(1205):
            item = await repo.create_case(draft(title=f"Solicitud de prueba {index:04}"))
            repo._cases[item["id"]]["created_at"] = "2026-09-18T04:30:00Z"
            repo._cases[item["id"]]["due_on"] = "2026-09-17"
        assert len(await repo.list_cases()) == 51
        report = await repo.case_report(
            filters={"received_from": "2026-09-17", "received_to": "2026-09-17"}
        )
        assert len(report["rows"]) == 1205
        report["local_date"] = "2026-09-17"
        assert report_summary(report)["overdue"] == 0
        report["local_date"] = "2026-09-18"
        assert report_summary(report)["overdue"] == 1205
        report["rows"][0]["status"] = "atendido"
        assert report_summary(report)["pending"] == report_summary(report)["overdue"] == 1204
        report["rows"][0]["title"] = '=HYPERLINK("https://example.invalid")'
        exported = list(csv.DictReader(io.StringIO(report_csv(report).decode("utf-8-sig"))))
        assert len(exported) == 1205
        assert len({row["Expediente"] for row in exported}) == 1205
        assert exported[0]["Asunto"].startswith("'=HYPERLINK")
        assert exported[0]["Ingreso (Chiclayo)"] == "17/09/2026 23:30:00"
        assert all("01234567" not in value for row in exported for value in row.values())

    asyncio.run(exercise())


@pytest.mark.parametrize("role", ["gestor", "consulta"])
def test_demo_exports_are_scoped_and_recheck_active_profile(role):
    async def exercise():
        repo = DemoRepository()
        actor = await repo.sign_in()
        repo._staff_profiles[0]["role"] = role
        report = await repo.case_report()
        assert len(report["rows"]) == 1
        assert report["rows"][0]["department_id"] == actor["department_id"]
        foreign = next(
            c for c in repo._cases.values() if c["department_id"] != actor["department_id"]
        )
        with pytest.raises(UserError, match="no está disponible"):
            await repo.case_receipt(foreign["id"])
        assert not (await repo.case_report(filters={"department_id": foreign["department_id"]}))[
            "rows"
        ]
        repo._staff_profiles[0]["is_active"] = False
        with pytest.raises(UserError, match="perfil municipal activo"):
            await repo.case_report()

    asyncio.run(exercise())


def test_receipt_handles_long_literal_text_and_current_state_without_contacts():
    async def exercise():
        repo = DemoRepository(seeded=False)
        await repo.sign_in()
        description = (
            "Información sobre el trámite: árboles, niños y señalización. " * 79
        ) + " FINAL DEL TEXTO <b>literal</b> & cierre."
        item = await repo.create_case(
            draft(description=description, email="privado@example.invalid", phone="999111222")
        )
        item = await repo.advance_case(
            item, "en_revision", item["department_id"], "Revisión interna del expediente de prueba."
        )
        receipt = await repo.case_receipt(item["id"])
        assert receipt["case"]["version"] == 2
        reader = PdfReader(io.BytesIO(receipt_pdf(receipt)))
        text = "\n".join(page.extract_text() for page in reader.pages)
        assert 2 <= len(reader.pages) <= 4
        for value in [
            "Constancia de registro",
            "****4567",
            "FINAL DEL TEXTO",
            "<b>literal</b>",
            "En revisión",
            "árboles",
            "DEMOSTRACIÓN",
        ]:
            assert value in text
        for value in ["01234567", "privado@example.invalid", "999111222"]:
            assert value not in text
        assert all(not page.get("/Annots") for page in reader.pages)

    asyncio.run(exercise())


@pytest.mark.parametrize("seeded", [False, True])
def test_summary_pdf_has_complete_totals_filters_and_no_applicant_data(seeded):
    async def exercise():
        repo = DemoRepository(seeded=seeded)
        await repo.sign_in()
        report = await repo.case_report()
        text = "\n".join(
            page.extract_text() for page in PdfReader(io.BytesIO(summary_pdf(report))).pages
        )
        assert "Reporte de expedientes" in text
        assert "Distribución por estado" in text
        assert "Distribución por área actual" in text
        assert "DEMOSTRACIÓN" in text
        assert "Solicitante de ejemplo" not in text
        if not seeded:
            assert "Sin resultados para estos filtros" in text

    asyncio.run(exercise())


def test_report_api_uses_one_authenticated_rpc_without_page_limits():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test"
        assert not request.url.params
        return httpx.Response(200, json={"rows": []})

    async def exercise():
        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler))
        repo.session = {
            "access_token": "test",
            "refresh_token": "test",
            "expires_at": time.time() + 3600,
        }
        await repo.case_report(
            "REP-2026", "recibido", filters={"assignee": "mine", "pending_only": True}
        )
        assert requests[0].url.path.endswith("/rpc/export_case_report")
        payload = json.loads(requests[0].content)["report_filters"]
        assert payload["query"] == "REP-2026" and payload["assignee"] == "mine"
        assert "limit" not in payload and "offset" not in payload
        case_id = str(uuid4())
        await repo.case_receipt(case_id)
        assert requests[1].url.path.endswith("/rpc/case_receipt")
        assert json.loads(requests[1].content) == {"case_id": case_id}
        await repo.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("width", [390, 1280])
def test_report_and_receipt_downloads_recheck_data_and_build_at_both_widths(width):
    async def exercise():
        page = PageStub()
        page.width = width
        app = MunicipalApp(page, Settings(), DemoRepository())
        app.profile = await app.repo.sign_in()
        app.departments = await app.repo.departments()
        app.shell()
        app.filters = {"priority": "alta"}
        saved = []

        async def save_file(**kwargs):
            saved.append(kwargs)

        app.picker = SimpleNamespace(save_file=save_file)
        await show_report(app)
        assert_valid_wrapping_layout(app.content)
        # Una modificación posterior a abrir el reporte se ve al descargar.
        selected = next(c for c in app.repo._cases.values() if c["priority"] == "alta")
        selected["title"] = "Asunto actualizado antes de descargar"
        for label, suffix in [("CSV completo", ".csv"), ("Resumen PDF", ".pdf")]:
            button = next(
                c
                for c in walk(app.content)
                if isinstance(c, (ft.FilledButton, ft.OutlinedButton)) and c.content == label
            )
            await button.on_click(SimpleNamespace(control=button))
            assert saved[-1]["file_name"].endswith(suffix)
            if suffix == ".csv":
                assert b"Asunto actualizado" in saved[-1]["src_bytes"]
        await app.detail(selected["id"])
        button = next(
            c
            for c in walk(app.content)
            if isinstance(c, ft.OutlinedButton) and c.content == "Constancia PDF"
        )
        await button.on_click(SimpleNamespace(control=button))
        assert saved[-1]["file_name"].startswith("constancia_DEMO-")
        assert saved[-1]["src_bytes"].startswith(b"%PDF-")
        app.repo._staff_profiles[0]["is_active"] = False
        before = len(saved)
        await button.on_click(SimpleNamespace(control=button))
        assert len(saved) == before
        assert "perfil municipal activo" in page.last_dialog.content.value
        await app.close()

    asyncio.run(exercise())


def test_report_labels_and_dates_are_unambiguous():
    repo = DemoRepository()

    async def exercise():
        await repo.sign_in()
        report = await repo.case_report(
            "solicitud", "recibido", filters={"due": "soon", "assignee": "mine"}
        )
        assert filter_description(report) == [
            "Búsqueda: solicitud",
            "Estado: Recibido",
            "Responsable: Asignados a mí",
            "Objetivo en próximos 3 días",
        ]
        assert local_timestamp("2026-09-18T02:00:00Z") == "17/09/2026 21:00:00"

    asyncio.run(exercise())
