import asyncio
from types import SimpleNamespace

import flet as ft
import pytest

from munigest.config import Settings
from munigest.demo import DemoRepository
from munigest.ui import MunicipalApp


class PageStub:
    width = 1200
    appbar = None
    drawer = None

    def __init__(self):
        self.controls = []
        self.services = []
        self.drawer_open = False

    def add(self, *items):
        self.controls.extend(items)

    def update(self):
        pass

    def show_dialog(self, dialog):
        self.last_dialog = dialog

    async def show_drawer(self):
        self.drawer_open = True

    async def close_drawer(self):
        self.drawer_open = False


def assert_valid_wrapping_layout(control):
    """Flutter Wrap no admite los Expanded/Flexible de una fila o columna Flex."""
    children = list(getattr(control, "controls", []))
    if isinstance(control, (ft.Row, ft.Column)) and control.wrap:
        assert not any(getattr(child, "expand", False) for child in children), (
            "Un control expandido dentro de wrap=True impide dibujar la pantalla."
        )
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        children.append(content)
    for child in children:
        assert_valid_wrapping_layout(child)


@pytest.mark.parametrize("seeded", [False, True], ids=["sin-expedientes", "con-expedientes"])
def test_all_screens_build_at_desktop_and_mobile_widths(seeded):
    async def exercise():
        for width in [390, 1280]:
            page = PageStub()
            page.width = width
            app = MunicipalApp(page, Settings(), DemoRepository(seeded=seeded))
            app.login()
            for control in page.controls:
                assert_valid_wrapping_layout(control)
            app.profile = await app.repo.sign_in()
            app.departments = await app.repo.departments()
            app.shell()
            for screen in [0, 1, 2, 3]:
                if width < 850:
                    assert asyncio.iscoroutinefunction(app.menu_button.on_click)
                    await app.menu_button.on_click(None)
                    assert page.drawer_open
                    page.drawer.selected_index = screen
                    await page.drawer.on_change(SimpleNamespace(control=page.drawer))
                else:
                    await app.nav_handler(screen)(None)
                assert not page.drawer_open
                assert app.screen == screen
                assert app.content.controls
                assert_valid_wrapping_layout(app.content)
            for entity in ["departments", "procedures", "staff_profiles"]:
                admin = app.admin_screen
                admin.entity = entity
                await admin.show()
                assert_valid_wrapping_layout(app.content)
                records = await app.repo.admin_records(entity)
                await admin.editor(records[0])
                assert_valid_wrapping_layout(app.content)
                if entity != "staff_profiles":
                    await admin.editor()
                    assert_valid_wrapping_layout(app.content)
            await app.new_handler(None)
            assert_valid_wrapping_layout(app.content)
            cases = await app.repo.list_cases()
            if cases:
                await app.detail(cases[0]["id"])
                assert_valid_wrapping_layout(app.content)
            app.resize()
            assert app.sidebar.visible == (width >= 850)
            await app.close()

    asyncio.run(exercise())


def test_navigation_marks_current_section_and_filters_survive_collapsing():
    def walk(control):
        yield control
        for child in getattr(control, "controls", []):
            yield from walk(child)
        content = getattr(control, "content", None)
        if isinstance(content, ft.Control):
            yield from walk(content)

    async def exercise():
        app = MunicipalApp(PageStub(), Settings(), DemoRepository())
        app.profile = await app.repo.sign_in()
        app.departments = await app.repo.departments()
        app.shell()
        await app.navigate(1)
        assert [button.tooltip for button in app.nav_buttons].count("Sección actual") == 1
        assert app.nav_buttons[1].tooltip == "Sección actual"
        tile = next(c for c in walk(app.content) if isinstance(c, ft.ExpansionTile))
        assert not tile.expanded and tile.maintain_state
        tile.expanded = True
        priority = next(
            c for c in walk(tile) if isinstance(c, ft.Dropdown) and c.label == "Prioridad"
        )
        priority.value = "alta"
        tile.expanded = False
        apply = next(
            c
            for c in walk(app.content)
            if isinstance(c, ft.FilledButton) and c.content == "Aplicar filtros"
        )
        await apply.on_click(SimpleNamespace(control=apply))
        assert app.filters["priority"] == "alta"
        assert all(row["priority"] == "alta" for row in app.rows)
        tile = next(c for c in walk(app.content) if isinstance(c, ft.ExpansionTile))
        assert tile.expanded
        await app.navigate(0)
        assert app.nav_buttons[0].tooltip == "Sección actual"
        assert app.nav_buttons[1].tooltip is None
        await app.close()

    asyncio.run(exercise())
