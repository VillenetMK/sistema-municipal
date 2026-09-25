"""Interfaz Flet compartida por web, escritorio y móvil."""

import asyncio
import logging
from datetime import datetime
from uuid import uuid4

import flet as ft

from munigest.config import Settings
from munigest.demo import DemoRepository
from munigest.design import (
    ACCENT,
    INK,
    LINE,
    MUTED,
    SOFT,
    STATUS_ICONS,
    SURFACE,
    brand,
    icon_badge,
    metric,
    panel,
    pill,
    section,
    small,
    theme,
)
from munigest.domain import (
    CHANNELS,
    PRIORITIES,
    ROLES,
    STATUSES,
    TRANSITIONS,
    SessionExpired,
    UserError,
)
from munigest.institution import INSTITUTION_NAME, OFFICIAL_RESOURCES, UNIT_TYPES
from munigest.repository import SupabaseRepository
from munigest.work_queue import due_notice, eligible_workers

NAV = [
    ("Resumen", ft.Icons.DASHBOARD_OUTLINED),
    ("Expedientes", ft.Icons.FOLDER_OPEN_OUTLINED),
    ("Áreas y trámites", ft.Icons.MENU_BOOK_OUTLINED),
]


def timestamp(value):
    from datetime import timedelta, timezone

    try:
        return (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            .astimezone(timezone(timedelta(hours=-5)))
            .strftime("%d/%m/%Y · %H:%M")
        )
    except (ValueError, TypeError):
        return str(value)


class MunicipalApp:
    def __init__(self, page, settings, repository=None):
        self.page = page
        self.settings = settings
        self.repo = repository or (
            DemoRepository() if settings.mode == "demo" else SupabaseRepository(settings)
        )
        self.profile = None
        self.departments = []
        self.procedures = []
        self.staff = []
        self.filters = {}
        self.institution = INSTITUTION_NAME
        self.screen = 0
        self.query = ""
        self.status = ""
        self.offset = 0
        self.rows = []
        self.sidebar = None
        self.menu_button = None
        self.nav_buttons = []
        self.login_hero = None
        self.login_card = None
        self.login_frame = None
        self.content_frame = None
        self.admin_screen = None
        self.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.picker = ft.FilePicker()
        page.title = settings.name
        page.theme = theme()
        page.theme_mode = ft.ThemeMode.LIGHT
        page.bgcolor = SURFACE
        page.padding = 0
        page.on_resize = self.resize
        page.on_close = self.close
        page.services.append(self.picker)

    async def close(self, _=None):
        await self.repo.close()

    def resize(self, _=None):
        mobile = (self.page.width or 1100) < 850
        if self.sidebar:
            self.sidebar.visible = not mobile
        if self.menu_button:
            self.menu_button.visible = mobile
        if self.login_hero:
            self.login_hero.visible = not mobile
        if self.login_card:
            self.login_card.padding = 24 if mobile else 36
        if self.login_frame:
            self.login_frame.width = 480 if mobile else 1040
        if self.content_frame:
            self.content_frame.padding = 16 if mobile else 28
        self.page.update()

    def notify(self, message):
        self.page.show_dialog(ft.SnackBar(ft.Text(message), duration=6500))

    async def guard(self, action, control=None):
        if control:
            control.disabled = True
            self.page.update()
        try:
            return await action()
        except SessionExpired as exc:
            self.profile = None
            self.login()
            self.notify(str(exc))
        except UserError as exc:
            self.notify(str(exc))
        except Exception as exc:
            logging.error("Operación de interfaz fallida: %s", type(exc).__name__)
            self.notify(
                "Ocurrió un error inesperado. Vuelve a intentarlo; si continúa, contacta al administrador."
            )
        finally:
            if control:
                control.disabled = False
            self.page.update()

    def login(self):
        self.admin_screen = None
        self.sidebar = self.menu_button = self.content_frame = None
        self.nav_buttons = []
        self.filters, self.query, self.status, self.offset = {}, "", "", 0
        self.page.appbar = None
        self.page.drawer = None
        self.page.controls.clear()
        identifier = ft.TextField(
            label="Usuario o correo",
            keyboard_type=ft.KeyboardType.TEXT,
            autofill_hints=ft.AutofillHint.USERNAME,
            max_length=254,
            counter="",
            prefix_icon=ft.Icons.PERSON_OUTLINE,
        )
        password = ft.TextField(
            label="Contraseña",
            password=True,
            can_reveal_password=True,
            autofill_hints=ft.AutofillHint.PASSWORD,
            prefix_icon=ft.Icons.LOCK_OUTLINE,
        )
        error = ft.Text("", color="#7B2222", visible=False)

        async def enter(e):
            async def work():
                error.visible = False
                try:
                    self.profile = await self.repo.sign_in(
                        identifier.value or "", password.value or ""
                    )
                    self.departments, settings = await asyncio.gather(
                        self.repo.departments(), self.repo.settings()
                    )
                    self.institution = settings["institution_name"]
                except UserError as exc:
                    error.value, error.visible = str(exc), True
                    return
                password.value = ""
                self.shell()
                await self.navigate(0)

            await self.guard(work, e.control)

        password.on_submit = enter
        is_demo = self.settings.mode == "demo"
        form = [
            brand(self.settings.name),
            ft.Divider(height=28, color=LINE),
            ft.Text(
                "Explora la mesa de partes" if is_demo else "Iniciar sesión",
                size=26,
                weight=ft.FontWeight.BOLD,
            ),
            small("Todo listo para continuar con tu trabajo."),
        ]
        if is_demo:
            form.extend(
                [
                    pill("Demostración", ft.Icons.SCIENCE_OUTLINED),
                    ft.Text(
                        "Practica con expedientes ficticios. Los cambios se conservan solo durante esta sesión.",
                        color=MUTED,
                    ),
                ]
            )
        else:
            form.extend([identifier, password])
        form.extend(
            [
                error,
                ft.FilledButton(
                    "Explorar demostración" if is_demo else "Ingresar",
                    icon=ft.Icons.ARROW_FORWARD,
                    on_click=enter,
                    width=float("inf"),
                    height=50,
                ),
            ]
        )
        if not is_demo:
            from munigest.account_ui import AccountScreen

            accounts = AccountScreen(self)
            form.extend(
                [
                    ft.TextButton(
                        "Olvidé mi contraseña", on_click=accounts.public_handler("recovery")
                    ),
                    ft.Divider(height=16, color=LINE),
                    small("¿Es tu primer ingreso?"),
                    ft.Row(
                        [
                            ft.TextButton(
                                "Activar invitación", on_click=accounts.public_handler("signup")
                            ),
                            ft.TextButton(
                                "Confirmar mi correo", on_click=accounts.public_handler("confirm")
                            ),
                        ],
                        wrap=True,
                        spacing=0,
                        run_spacing=0,
                    ),
                ]
            )
        # Una composición amplia en escritorio y una sola columna en el teléfono.
        # El formulario conserva su estado al cambiar el tamaño de la ventana.
        mobile = (self.page.width or 1100) < 850
        self.login_card = panel(form, expand=True, padding=24 if mobile else 36, border=None)
        self.login_hero = ft.Container(
            ft.Column(
                [
                    icon_badge(ft.Icons.ACCOUNT_BALANCE_OUTLINED, dark=True, size=56),
                    ft.Text(
                        "MUNICIPALIDAD PROVINCIAL\nDE CHICLAYO",
                        size=12,
                        color="#D6E7E4",
                        weight=ft.FontWeight.W_600,
                    ),
                    ft.Text(
                        "Cada solicitud,\nun recorrido claro.",
                        size=38,
                        weight=ft.FontWeight.BOLD,
                        color="#FFFFFF",
                    ),
                    ft.Text(
                        "Un espacio para recibir, organizar y dar seguimiento a las solicitudes ciudadanas.",
                        size=16,
                        color="#D6E7E4",
                    ),
                    ft.Divider(color="#486269", height=24),
                    *[
                        ft.Row(
                            [
                                icon_badge(icon, dark=True, size=36),
                                ft.Column(
                                    [
                                        ft.Text(title, color="#FFFFFF", weight=ft.FontWeight.W_600),
                                        ft.Text(description, size=12, color="#D6E7E4"),
                                    ],
                                    spacing=3,
                                    expand=True,
                                ),
                            ],
                            spacing=12,
                        )
                        for icon, title, description in [
                            (
                                ft.Icons.ADD_TASK,
                                "Recibe y registra",
                                "Cada expediente tiene un código único.",
                            ),
                            (
                                ft.Icons.FOLDER_OPEN_OUTLINED,
                                "Organiza la atención",
                                "Áreas, responsables y documentos juntos.",
                            ),
                            (
                                ft.Icons.HISTORY,
                                "Sigue cada avance",
                                "Consulta las actuaciones de cada solicitud.",
                            ),
                        ]
                    ],
                ],
                spacing=20,
            ),
            bgcolor=INK,
            padding=36,
            expand=True,
            visible=not mobile,
        )
        self.login_frame = ft.Container(
            ft.Row(
                [self.login_hero, self.login_card],
                spacing=0,
                intrinsic_height=True,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            width=480 if mobile else 1040,
            border=ft.Border.all(1, LINE),
            border_radius=20,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        self.page.add(
            ft.SafeArea(
                ft.Container(
                    ft.Column(
                        [
                            self.login_frame,
                            small("Piloto de gestión interna · Acceso para personal autorizado"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        scroll=ft.ScrollMode.AUTO,
                        spacing=20,
                    ),
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                ),
                expand=True,
            )
        )
        self.page.update()

    async def logout(self, e):
        async def work():
            try:
                await self.repo.sign_out()
            finally:
                self.profile = None
                self.login()

        await self.guard(work)

    def nav_handler(self, index):
        async def handler(_):
            await self.page.close_drawer()
            await self.guard(lambda: self.navigate(index))

        return handler

    def shell(self):
        self.page.controls.clear()
        self.login_hero = self.login_card = self.login_frame = None
        mobile = (self.page.width or 1100) < 850

        async def open_menu(_):
            await self.page.show_drawer()

        self.menu_button = ft.IconButton(
            ft.Icons.MENU,
            tooltip="Abrir menú",
            visible=mobile,
            on_click=open_menu,
        )
        self.page.appbar = ft.AppBar(
            leading=self.menu_button,
            automatically_imply_leading=False,
            title=ft.Text(self.settings.name, size=20, weight=ft.FontWeight.BOLD, color=INK),
            bgcolor="#FFFFFF",
            elevation=0,
            toolbar_height=64,
            actions=[ft.IconButton(ft.Icons.LOGOUT, tooltip="Cerrar sesión", on_click=self.logout)],
        )

        async def drawer_change(e):
            await self.page.close_drawer()
            await self.guard(lambda: self.navigate(e.control.selected_index))

        navigation = NAV + (
            [("Administración", ft.Icons.SETTINGS_OUTLINED)]
            if self.profile["role"] == "admin"
            else []
        )
        self.page.drawer = ft.NavigationDrawer(
            controls=[
                ft.NavigationDrawerDestination(label=name, icon=icon) for name, icon in navigation
            ],
            on_change=drawer_change,
            bgcolor="#FFFFFF",
            indicator_color=SOFT,
        )
        nav_controls = [
            icon_badge(ft.Icons.ACCOUNT_BALANCE_OUTLINED),
            ft.Text(self.institution, size=16, weight=ft.FontWeight.W_600, color=INK),
            small("Mesa de partes y seguimiento"),
            ft.Divider(color=LINE, height=28),
            ft.Text("ESPACIO DE TRABAJO", size=10, weight=ft.FontWeight.BOLD, color=MUTED),
        ]
        self.nav_buttons = [
            ft.TextButton(name, icon=icon, on_click=self.nav_handler(i), width=224, height=48)
            for i, (name, icon) in enumerate(navigation)
        ]
        nav_controls += self.nav_buttons
        nav_controls += [
            ft.Container(expand=True),
            ft.Divider(color=LINE),
            ft.Row(
                [
                    icon_badge(ft.Icons.PERSON_OUTLINE, size=36),
                    ft.Column(
                        [
                            ft.Text(
                                self.profile["display_name"], weight=ft.FontWeight.W_600, size=13
                            ),
                            small(ROLES[self.profile["role"]]),
                        ],
                        expand=True,
                        spacing=3,
                    ),
                ],
                spacing=10,
            ),
        ]
        self.sidebar = ft.Container(
            ft.Column(nav_controls, expand=True, spacing=10),
            width=264,
            padding=20,
            bgcolor="#FFFFFF",
            border=ft.Border(right=ft.BorderSide(1, LINE)),
            visible=not mobile,
        )
        main = ft.Column(expand=True, spacing=0)
        if self.settings.mode == "demo":
            main.controls.append(
                ft.Container(
                    ft.Text(
                        "DEMOSTRACIÓN · Datos ficticios y cambios temporales",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=INK,
                    ),
                    bgcolor="#E2ECE8",
                    padding=12,
                )
            )
        self.content_frame = ft.Container(
            ft.Container(self.content, width=1240, expand=True),
            expand=True,
            padding=16 if mobile else 28,
            alignment=ft.Alignment.TOP_CENTER,
        )
        main.controls.append(self.content_frame)
        self.page.add(
            ft.SafeArea(
                ft.Row([self.sidebar, ft.Container(main, expand=True)], spacing=0, expand=True),
                expand=True,
            )
        )
        self.page.update()

    def update_navigation(self, index=None):
        if index is not None:
            self.screen = index
        if self.page.drawer:
            self.page.drawer.selected_index = self.screen
        for i, button in enumerate(self.nav_buttons):
            active = i == self.screen
            button.style = ft.ButtonStyle(
                bgcolor=SOFT if active else "#FFFFFF",
                color=INK if active else MUTED,
                side=ft.BorderSide(2 if active else 0, ACCENT if active else "#FFFFFF"),
                shape=ft.RoundedRectangleBorder(radius=10),
                alignment=ft.Alignment.CENTER_LEFT,
                padding=ft.Padding.symmetric(horizontal=14),
                text_style=ft.TextStyle(
                    size=14, weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_500
                ),
            )
            button.tooltip = "Sección actual" if active else None

    def heading(self, title, subtitle, actions=None):
        return ft.Column(
            [
                ft.Text("GESTIÓN MUNICIPAL", size=10, weight=ft.FontWeight.W_600, color=MUTED),
                ft.Text(title, size=26, weight=ft.FontWeight.BOLD, color=INK),
                small(subtitle),
            ]
            + (
                [
                    ft.Container(
                        ft.Row(actions, wrap=True, spacing=10, run_spacing=10),
                        padding=ft.Padding.only(top=8),
                    )
                ]
                if actions
                else []
            ),
            spacing=6,
        )

    async def navigate(self, index):
        if index == 3 and (not self.profile or self.profile["role"] != "admin"):
            raise UserError("Solo un administrador puede abrir Administración.")
        self.update_navigation(index)
        self.content.controls = [ft.ProgressBar(), small("Cargando información…")]
        self.page.update()
        if index == 0:
            await self.dashboard()
        elif index == 1:
            await self.inbox()
        elif index == 2:
            await self.catalog()
        elif index == 3:
            from munigest.admin_ui import AdministrationScreen

            if self.admin_screen is None:
                self.admin_screen = AdministrationScreen(self)
            await self.admin_screen.show()
        self.page.update()

    async def new_handler(self, _):
        async def work():
            self.departments, self.procedures, self.staff = await asyncio.gather(
                self.repo.departments(), self.repo.procedures(), self.repo.staff_directory()
            )
            self.new_case()

        await self.guard(work)

    def can_register(self):
        return self.profile["role"] in {"admin", "mesa_partes"}

    async def dashboard(self):
        metrics, recent = await asyncio.gather(self.repo.metrics(), self.repo.list_cases(limit=5))
        stats = []
        for label, key, icon, caption in [
            ("Expedientes", "total", ft.Icons.FOLDER_OPEN_OUTLINED, "Disponibles para tu perfil"),
            ("Pendientes", "pending", ft.Icons.SCHEDULE, "Por continuar su atención"),
            ("Objetivo vencido", "overdue", ft.Icons.PRIORITY_HIGH, "Fecha interna superada"),
            ("Atendidos", "resolved", ft.Icons.TASK_ALT, "Con atención registrada"),
        ]:
            stats.append(metric(label, metrics[key], icon, caption, featured=key == "pending"))
        actions = (
            [ft.FilledButton("Registrar solicitud", icon=ft.Icons.ADD, on_click=self.new_handler)]
            if self.can_register()
            else []
        )
        actions.append(
            ft.OutlinedButton(
                "Abrir bandeja", icon=ft.Icons.FOLDER_OPEN_OUTLINED, on_click=self.nav_handler(1)
            )
        )
        self.content.controls = [
            self.heading(
                "Tu jornada, en orden",
                "Resumen de los expedientes disponibles para tu perfil.",
                actions,
            ),
            ft.ResponsiveRow(stats, spacing=12, run_spacing=12),
            small(
                "Los vencimientos se calculan sobre la fecha objetivo interna registrada; no representan plazos legales."
            ),
            section("Actividad reciente", ft.Icons.HISTORY, "Los últimos expedientes registrados"),
        ]
        self.content.controls.extend(
            [self.case_card(x) for x in recent]
            or [
                self.empty(
                    "Aún no hay expedientes",
                    "Registra la primera solicitud para comenzar su seguimiento.",
                )
            ]
        )

    def empty(self, title, message):
        return panel(
            [
                section(title, ft.Icons.INBOX_OUTLINED, message),
            ]
        )

    def open_handler(self, case_id):
        async def handler(_):
            await self.guard(lambda: self.detail(case_id, reset_scroll=True))

        return handler

    def case_card(self, item):
        tags = [pill(STATUSES[item["status"]], STATUS_ICONS.get(item["status"]))]
        notice = due_notice(item)
        if notice:
            tags.append(pill(notice, ft.Icons.SCHEDULE))
        return ft.Container(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                item["reference"],
                                weight=ft.FontWeight.BOLD,
                                color=INK,
                                size=12,
                            ),
                            small(timestamp(item["created_at"])),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    ),
                    ft.Text(item["title"], size=17, weight=ft.FontWeight.W_600, color=INK),
                    ft.Row(tags, wrap=True, spacing=10),
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.BUSINESS_OUTLINED, size=16, color=MUTED),
                            ft.Text(item["department"]["name"], size=13, color=MUTED, expand=True),
                        ],
                        spacing=8,
                    ),
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.PERSON_OUTLINE, size=16, color=MUTED),
                            ft.Text(
                                (item.get("assignee") or {}).get("display_name")
                                or "Pendiente de asignación",
                                size=13,
                                color=MUTED,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                    small(
                        f"Trámite: {(item.get('procedure_snapshot') or {}).get('name') or 'Sin trámite vinculado'}"
                    ),
                    ft.Divider(height=1, color=LINE),
                    ft.Row(
                        [
                            pill(
                                f"Prioridad {PRIORITIES[item['priority']]}", ft.Icons.FLAG_OUTLINED
                            ),
                            ft.TextButton(
                                "Abrir expediente",
                                icon=ft.Icons.CHEVRON_RIGHT,
                                on_click=self.open_handler(item["id"]),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    ),
                ],
                spacing=10,
            ),
            bgcolor="#FFFFFF",
            border=ft.Border.all(1, LINE),
            border_radius=16,
            padding=20,
        )

    async def inbox(self):
        from munigest.work_ui import show_inbox

        await show_inbox(self)

    def new_case(self):
        if not self.can_register():
            self.notify("Tu perfil no puede registrar solicitudes.")
            return
        self.update_navigation(1)
        request_id = str(uuid4())
        fields = {
            "procedure_id": ft.Dropdown(
                label="Trámite",
                value=next((p["id"] for p in self.procedures if p["code"] == "GENERAL"), None),
                options=[ft.DropdownOption(p["id"], p["name"]) for p in self.procedures],
            ),
            "assigned_to": ft.Dropdown(
                label="Responsable (opcional)",
                value="",
                options=[ft.DropdownOption("", "Pendiente de asignación")],
            ),
            "document_type": ft.Dropdown(
                label="Tipo de documento",
                value="DNI",
                options=[ft.DropdownOption(x) for x in ["DNI", "RUC", "CE", "PAS"]],
            ),
            "document_number": ft.TextField(label="Número de documento", max_length=15),
            "applicant_name": ft.TextField(label="Nombre completo o razón social", max_length=180),
            "email": ft.TextField(
                label="Correo de contacto (opcional)",
                keyboard_type=ft.KeyboardType.EMAIL,
                max_length=254,
            ),
            "phone": ft.TextField(
                label="Teléfono (opcional)", keyboard_type=ft.KeyboardType.PHONE, max_length=20
            ),
            "title": ft.TextField(label="Asunto", max_length=160),
            "description": ft.TextField(
                label="Descripción de la solicitud",
                multiline=True,
                min_lines=3,
                max_lines=7,
                max_length=5000,
            ),
            "department_id": ft.Dropdown(
                label="Área de destino",
                options=[ft.DropdownOption(x["id"], x["name"]) for x in self.departments],
            ),
            "channel": ft.Dropdown(
                label="Canal de ingreso",
                value="presencial",
                options=[ft.DropdownOption(k, v) for k, v in CHANNELS.items()],
            ),
            "priority": ft.Dropdown(
                label="Prioridad",
                value="normal",
                options=[ft.DropdownOption(k, v) for k, v in PRIORITIES.items()],
            ),
            "due_on": ft.TextField(
                label="Fecha objetivo interna (opcional)", hint_text="AAAA-MM-DD", max_length=10
            ),
        }
        error = ft.Text("", color="#7B2222", visible=False)

        def refresh_workers():
            fields["assigned_to"].value = ""
            fields["assigned_to"].options = [ft.DropdownOption("", "Pendiente de asignación")] + [
                ft.DropdownOption(s["user_id"], s["display_name"])
                for s in eligible_workers(self.staff, fields["department_id"].value)
            ]

        async def department_changed(_):
            refresh_workers()
            self.page.update()

        async def procedure_changed(_):
            procedure = next(
                (p for p in self.procedures if p["id"] == fields["procedure_id"].value), None
            )
            if procedure and procedure.get("department_id"):
                fields["department_id"].value = procedure["department_id"]
                refresh_workers()
            self.page.update()

        fields["department_id"].on_select = department_changed
        fields["procedure_id"].on_select = procedure_changed
        initial_procedure = next(
            (p for p in self.procedures if p["id"] == fields["procedure_id"].value), None
        )
        if initial_procedure and initial_procedure.get("department_id"):
            fields["department_id"].value = initial_procedure["department_id"]
            refresh_workers()

        async def submit(e):
            async def work():
                error.visible = False
                try:
                    if not fields["procedure_id"].value:
                        raise UserError("Selecciona un trámite activo del catálogo.")
                    result = await self.repo.create_case(
                        {k: v.value for k, v in fields.items()} | {"request_id": request_id}
                    )
                except UserError as exc:
                    error.value, error.visible = str(exc), True
                    return
                self.notify(f"Expediente registrado: {result['reference']}")
                await self.detail(result["id"], reset_scroll=True)

            await self.guard(work, e.control)

        for field in fields.values():
            field.col = {"xs": 12, "md": 6}
        fields["applicant_name"].col = 12
        fields["title"].col = 12
        fields["description"].col = 12
        self.content.controls = [
            self.heading(
                "Registrar solicitud",
                "El código se genera al guardar. Podrás adjuntar documentos después del registro.",
                [
                    ft.TextButton(
                        "Volver a la bandeja",
                        icon=ft.Icons.ARROW_BACK,
                        on_click=self.nav_handler(1),
                    )
                ],
            ),
            panel(
                [
                    section(
                        "1. Solicitante",
                        ft.Icons.PERSON_OUTLINE,
                        "Identificación y datos de contacto",
                    ),
                    ft.ResponsiveRow(
                        [
                            fields[x]
                            for x in [
                                "document_type",
                                "document_number",
                                "applicant_name",
                                "email",
                                "phone",
                            ]
                        ],
                        run_spacing=16,
                    ),
                ]
            ),
            panel(
                [
                    section(
                        "2. Solicitud y destino",
                        ft.Icons.EDIT_NOTE,
                        "Información para iniciar el seguimiento",
                    ),
                    ft.ResponsiveRow(
                        [
                            fields[x]
                            for x in [
                                "procedure_id",
                                "title",
                                "description",
                                "department_id",
                                "assigned_to",
                                "channel",
                                "priority",
                                "due_on",
                            ]
                        ],
                        run_spacing=16,
                    ),
                    small(
                        "La fecha objetivo organiza el trabajo interno. Los requisitos y plazos legales se validan con el TUPA de la entidad."
                    ),
                    error,
                    ft.FilledButton(
                        "Guardar y generar expediente",
                        icon=ft.Icons.SAVE_OUTLINED,
                        on_click=submit,
                        height=48,
                    ),
                ]
            ),
        ]
        self.page.update()

    async def detail(self, case_id, *, reset_scroll=False):
        from munigest.work_ui import work_event_lines, work_panel

        item, events, documents, areas = await asyncio.gather(
            self.repo.get_case(case_id),
            self.repo.events(case_id),
            self.repo.documents(case_id),
            self.repo.departments(include_inactive=True),
        )
        applicant = item["applicant"]
        self.update_navigation(1)
        can_change = self.profile["role"] != "consulta" and item["status"] != "archivado"
        can_upload = can_change and item["status"] != "atendido"
        options = [item["status"], *TRANSITIONS[item["status"]]]
        target = ft.Dropdown(
            label="Estado",
            value=item["status"],
            options=[ft.DropdownOption(k, STATUSES[k]) for k in options],
        )
        department = ft.Dropdown(
            label="Área de destino",
            value=item["department_id"],
            options=[
                ft.DropdownOption(x["id"], x["name"])
                for x in areas
                if x["is_active"] or x["id"] == item["department_id"]
            ],
        )
        note = ft.TextField(
            label="Motivo, observación o respuesta",
            multiline=True,
            min_lines=3,
            max_lines=6,
            max_length=2000,
        )

        async def receipt(e):
            from munigest.report_ui import download_receipt

            await download_receipt(self, case_id, e.control)

        async def update(e):
            async def work():
                await self.repo.advance_case(item, target.value, department.value, note.value or "")
                self.notify("Actuación registrada en el historial.")
                if department.value != item["department_id"] and self.profile["role"] == "gestor":
                    await self.navigate(1)
                else:
                    await self.detail(case_id)

            await self.guard(work, e.control)

        async def upload(e):
            async def work():
                files = await self.picker.pick_files(
                    allow_multiple=False,
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["pdf", "png", "jpg", "jpeg"],
                    with_data=True,
                )
                if not files:
                    return
                if files[0].size > 10 * 1024 * 1024:
                    raise UserError("El tamaño máximo permitido es 10 MB.")
                if not files[0].bytes:
                    raise UserError(
                        "No se pudo leer el archivo seleccionado. Intenta seleccionarlo de nuevo."
                    )
                await self.repo.upload_document(case_id, files[0].name, files[0].bytes)
                self.notify("Documento adjuntado.")
                await self.detail(case_id)

            await self.guard(work, e.control)

        def downloader(document):
            async def handler(e):
                async def work():
                    content = await self.repo.download_document(document)
                    await self.picker.save_file(file_name=document["file_name"], src_bytes=content)

                await self.guard(work, e.control)

            return handler

        timeline = []
        for event in events:
            area = next(
                (d["name"] for d in areas if d["id"] == event.get("to_department_id")),
                "",
            )
            timeline += [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.HISTORY, size=18),
                        ft.Text(
                            f"{STATUSES.get(event['to_status'], event['to_status'])} · {event['action']}",
                            weight=ft.FontWeight.W_600,
                            expand=True,
                        ),
                    ],
                ),
                small(f"{timestamp(event['created_at'])} · {event['actor_name']}"),
                ft.Text(event["note"], selectable=True),
                *work_event_lines(event),
                small(area),
                ft.Divider(color=LINE),
            ]
        document_controls = [
            section(
                "Documentos", ft.Icons.ATTACH_FILE, "PDF, PNG o JPEG · máximo 10 MB por archivo"
            ),
        ]
        if can_upload:
            document_controls.append(
                ft.OutlinedButton("Adjuntar documento", icon=ft.Icons.ATTACH_FILE, on_click=upload)
            )
        document_controls += [
            ft.Row(
                [
                    ft.Icon(ft.Icons.DESCRIPTION_OUTLINED),
                    ft.Column(
                        [ft.Text(doc["file_name"]), small(f"{doc['size_bytes'] / 1024:.1f} KB")],
                        expand=True,
                    ),
                    ft.IconButton(
                        ft.Icons.DOWNLOAD,
                        tooltip=f"Descargar {doc['file_name']}",
                        on_click=downloader(doc),
                    ),
                ]
            )
            for doc in documents
        ]
        if not documents:
            document_controls.append(small("Todavía no hay documentos adjuntos."))
        self.content.controls = [
            self.heading(
                item["reference"],
                item["title"],
                [
                    ft.TextButton(
                        "Volver a la bandeja",
                        icon=ft.Icons.ARROW_BACK,
                        on_click=self.nav_handler(1),
                    ),
                    ft.OutlinedButton(
                        "Constancia PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=receipt
                    ),
                ],
            ),
            ft.Row(
                [
                    pill(STATUSES[item["status"]], STATUS_ICONS.get(item["status"])),
                    pill(f"Prioridad {PRIORITIES[item['priority']]}", ft.Icons.FLAG_OUTLINED),
                    small(item["department"]["name"]),
                ],
                wrap=True,
            ),
            panel(
                [
                    section("Solicitud", ft.Icons.DESCRIPTION_OUTLINED),
                    ft.Text(item["description"], selectable=True),
                    ft.Divider(color=LINE),
                    ft.Text(applicant["full_name"], weight=ft.FontWeight.BOLD),
                    small(f"{applicant['document_type']}: {applicant['document_number']}"),
                    small(
                        f"Contacto: {applicant.get('email') or 'Sin correo'} · {applicant.get('phone') or 'Sin teléfono'}"
                    ),
                    small(
                        f"Ingreso: {timestamp(item['created_at'])} · {CHANNELS[item['channel']]}"
                    ),
                    small(f"Fecha objetivo interna: {item.get('due_on') or 'No asignada'}"),
                ]
            ),
            panel(document_controls),
            await work_panel(self, item),
        ]
        if can_change:
            self.content.controls.append(
                panel(
                    [
                        section("Registrar actuación", ft.Icons.EDIT_NOTE),
                        target,
                        department,
                        note,
                        ft.FilledButton(
                            "Guardar actuación", icon=ft.Icons.TASK_ALT, on_click=update
                        ),
                    ]
                )
            )
        self.content.controls.append(
            panel(
                [
                    section("Historial del expediente", ft.Icons.HISTORY),
                    *timeline,
                ]
            )
        )
        self.page.update()

        if reset_scroll:
            # Abrir desde una bandeja desplazada debe mostrar la cabecera del expediente.
            await self.content.scroll_to(offset=0)

    async def catalog(self):
        procedures, self.departments = await asyncio.gather(
            self.repo.procedures(), self.repo.departments()
        )
        controls = [
            self.heading(
                "Áreas y trámites",
                "Directorio de destinos y catálogo de referencia para mesa de partes.",
            ),
            panel(
                [
                    ft.Text(self.institution, size=20, weight=ft.FontWeight.W_600),
                    small("Fuentes oficiales para orientar la atención"),
                    *[
                        ft.TextButton(label, icon=ft.Icons.OPEN_IN_NEW, url=url)
                        for label, url in OFFICIAL_RESOURCES
                    ],
                    small(
                        "Estos enlaces abren portales de la MPCH. Los registros del piloto "
                        "todavía no se sincronizan con el SGD municipal."
                    ),
                ]
            ),
            panel(
                [
                    section("Áreas disponibles", ft.Icons.ACCOUNT_TREE_OUTLINED),
                    small(
                        "Selección inicial de gerencias del organigrama publicado "
                        "y un punto de recepción para el piloto."
                    ),
                    *[
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.ACCOUNT_BALANCE_OUTLINED),
                            title=ft.Text(d["name"]),
                            subtitle=ft.Text(
                                f"{d['code']} · {UNIT_TYPES.get(d.get('unit_type'), 'Área de referencia')}"
                            ),
                        )
                        for d in self.departments
                    ],
                ]
            ),
            section("Catálogo de trámites", ft.Icons.MENU_BOOK_OUTLINED),
        ]
        for item in procedures:
            department = next(
                (d["name"] for d in self.departments if d["id"] == item.get("department_id")),
                "Sin área asignada",
            )
            fee = (
                f"S/ {float(item['fee_pen']):,.2f}"
                if item.get("fee_pen") is not None
                else "Sin importe registrado"
            )
            deadline = (
                f"{item['deadline_days']} días"
                if item.get("deadline_days") is not None
                else "Sin plazo registrado"
            )
            controls.append(
                panel(
                    [
                        ft.Text(item["name"], size=18, weight=ft.FontWeight.W_600),
                        pill(
                            "Ficha oficial registrada"
                            if item["is_official"]
                            else "Referencia general"
                        ),
                        ft.Text(item["requirements"]),
                        small(f"{department} · {fee} · {deadline}"),
                        small(
                            "Datos de la ficha: consulta el sustento antes de utilizarlos. No generan cobros ni vencimientos automáticos."
                        ),
                        small(
                            item.get("legal_basis")
                            or "Catálogo pendiente de validación por la MPCH. Consulta el TUPA enlazado."
                        ),
                    ]
                )
            )
        self.content.controls = controls


async def main(page: ft.Page):
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        page.add(ft.Text("Configuración pendiente", size=24), ft.Text(str(exc)))
        return
    app = MunicipalApp(page, settings)
    app.login()
