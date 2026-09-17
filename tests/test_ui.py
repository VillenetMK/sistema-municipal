import asyncio
from types import SimpleNamespace

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

    async def show_drawer(self):
        self.drawer_open = True

    async def close_drawer(self):
        self.drawer_open = False


def test_all_screens_build_at_desktop_and_mobile_widths():
    async def exercise():
        for width in [390, 1280]:
            page = PageStub()
            page.width = width
            app = MunicipalApp(page, Settings(), DemoRepository())
            app.login()
            app.profile = await app.repo.sign_in()
            app.departments = await app.repo.departments()
            app.shell()
            for screen in [0, 1, 2]:
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
            app.new_case()
            case = (await app.repo.list_cases())[0]
            await app.detail(case["id"])
            app.resize()
            assert app.sidebar.visible == (width >= 850)
            await app.close()

    asyncio.run(exercise())
