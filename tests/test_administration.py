import asyncio
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import flet as ft
import httpx
import pytest
from test_ui import PageStub, assert_valid_wrapping_layout

from munigest.administration import validate_admin_record
from munigest.config import Settings
from munigest.demo import DemoRepository
from munigest.domain import UserError
from munigest.repository import SupabaseRepository
from munigest.ui import MunicipalApp


def area(**changes):
    return {
        "id": str(uuid4()),
        "code": "QA",
        "name": "Área de prueba",
        "is_active": True,
        "unit_type": "referencia",
        "source_url": None,
        **changes,
    }


def test_demo_admin_preserves_history_and_prevents_stale_or_self_lockout_changes():
    async def exercise():
        repo = DemoRepository(seeded=False)
        own = await repo.sign_in()
        original = await repo.admin_save("departments", area(), 0, "Alta para prueba del catálogo.")
        changed = await repo.admin_save(
            "departments", original | {"name": "Área actualizada"}, 1, "Cambio de nombre del área."
        )
        with pytest.raises(UserError, match="Otro usuario"):
            await repo.admin_save("departments", original, 1, "Intento con versión anterior.")
        history = await repo.admin_history("departments", original["id"])
        assert len(history) == 2
        assert history[0]["before_data"] == original
        assert history[0]["after_data"] == changed
        assert history[0]["actor_id"] == own["user_id"]
        with pytest.raises(UserError, match="propia cuenta"):
            await repo.admin_save(
                "staff_profiles", own | {"is_active": False}, 1, "Desactivación accidental propia."
            )
        with pytest.raises(UserError, match="propia cuenta"):
            await repo.admin_save(
                "staff_profiles",
                own | {"role": "consulta"},
                1,
                "Retirada accidental del rol propio.",
            )
        original["name"] = "Cambio fuera del repositorio"
        assert (await repo.admin_records("departments", "actualizada"))[0][
            "name"
        ] == "Área actualizada"
        await repo.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("changes", [{"source_url": "javascript:alert(1)"}, {"is_active": "false"}])
def test_invalid_admin_fields_do_not_silently_change_meaning(changes):
    with pytest.raises(UserError):
        validate_admin_record("departments", area(**changes))


@pytest.mark.parametrize(
    "field,value",
    [("fee_pen", "NaN"), ("fee_pen", "1.001"), ("deadline_days", "1.5"), ("deadline_days", "0")],
)
def test_invalid_catalog_numbers_are_rejected(field, value):
    with pytest.raises(UserError):
        validate_admin_record("procedures", area() | {"is_official": False, field: value})


def test_official_fiche_requires_source_and_blank_fee_differs_from_free():
    draft = area() | {"is_official": True}
    with pytest.raises(UserError, match="sustento"):
        validate_admin_record("procedures", draft)
    draft["legal_basis"] = "Referencia documental del procedimiento."
    assert validate_admin_record("procedures", draft)["fee_pen"] is None
    assert validate_admin_record("procedures", draft | {"fee_pen": 0})["fee_pen"] == "0"


def test_repository_sends_authorized_rpc_with_version_and_reason_only():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer session-for-user"
        return httpx.Response(200, json={"version": 2})

    async def exercise():
        settings = Settings(
            mode="supabase",
            url="https://lxvmwjcqdjoidgpinmgm.supabase.co",
            key="sb_publishable_test",
        )
        repo = SupabaseRepository(settings, httpx.MockTransport(handler))
        repo.session = {
            "access_token": "session-for-user",
            "refresh_token": "r",
            "expires_at": time.time() + 3600,
        }
        draft = area()
        try:
            await repo.admin_save(
                "departments",
                draft | {"version": 999, "role": "admin"},
                1,
                "Corrección autorizada del nombre.",
            )
            assert len(calls) == 1
            assert calls[0].url.path == "/rest/v1/rpc/admin_save_record"
            assert json.loads(calls[0].content) == {
                "entity": "departments",
                "payload": draft,
                "expected_version": 1,
                "reason": "Corrección autorizada del nombre.",
            }
        finally:
            await repo.close()

    asyncio.run(exercise())


def walk(control):
    yield control
    children = list(getattr(control, "controls", []))
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        children.append(content)
    for child in children:
        yield from walk(child)


def test_admin_form_saves_then_uses_confirmed_version_for_next_edit():
    async def exercise():
        app = MunicipalApp(PageStub(), Settings(), DemoRepository(seeded=False))
        app.profile = await app.repo.sign_in()
        app.departments = await app.repo.departments()
        app.shell()
        await app.navigate(3)
        await app.admin_screen.editor()

        async def fill_and_save(values):
            controls = list(walk(app.content))
            for label, value in values.items():
                next(
                    c for c in controls if isinstance(c, ft.TextField) and c.label == label
                ).value = value
            button = next(
                c
                for c in controls
                if isinstance(c, ft.FilledButton) and c.content == "Guardar cambios"
            )
            await button.on_click(SimpleNamespace(control=button))
            assert_valid_wrapping_layout(app.content)

        await fill_and_save(
            {
                "Código interno": "QATEST",
                "Nombre": "Área de prueba UI",
                "Motivo del cambio": "Alta del área desde el formulario.",
            }
        )
        row = (await app.repo.admin_records("departments", "QATEST"))[0]
        assert row["version"] == 1
        await fill_and_save(
            {
                "Nombre": "Área actualizada desde UI",
                "Motivo del cambio": "Corrección del nombre desde el formulario.",
            }
        )
        row = (await app.repo.admin_records("departments", "QATEST"))[0]
        assert row["version"] == 2
        assert len(await app.repo.admin_history("departments", row["id"])) == 2
        await app.close()

    asyncio.run(exercise())


def test_consulta_cannot_open_admin_even_if_navigation_is_called_directly():
    async def exercise():
        repo = DemoRepository(seeded=False)
        app = MunicipalApp(PageStub(), Settings(), repo)
        app.profile = await repo.sign_in()
        app.profile["role"] = "consulta"
        app.shell()
        assert len(app.page.drawer.controls) == 3
        with pytest.raises(UserError, match="administrador"):
            await app.navigate(3)
        repo._staff_profiles[0]["role"] = "consulta"
        with pytest.raises(UserError, match="administrador activo"):
            await repo.admin_records("staff_profiles")
        await app.close()

    asyncio.run(exercise())
