"""Interfaz Flet compartida por web, escritorio y móvil."""

import asyncio
import logging
from datetime import datetime
from uuid import uuid4

import flet as ft

from munigest.config import Settings
from munigest.demo import DemoRepository
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

INK = "#192A32"
MUTED = "#53616A"
LINE = "#DCE2E4"
SURFACE = "#F4F6F7"
ACCENT = "#164D48"
NAV = [
    ("Resumen", ft.Icons.DASHBOARD_OUTLINED),
    ("Expedientes", ft.Icons.FOLDER_OPEN_OUTLINED),
    ("Áreas y trámites", ft.Icons.MENU_BOOK_OUTLINED),
]


def panel(controls, **kwargs):
    return ft.Container(
        content=ft.Column(controls, spacing=14),
        bgcolor="#FFFFFF",
        border=ft.Border.all(1, LINE),
        border_radius=16,
        padding=24,
        **kwargs,
    )


def small(text):
    return ft.Text(text, size=13, color=MUTED)


def pill(text, icon=None):
    return ft.Container(
        ft.Row(
            ([ft.Icon(icon, size=15, color=INK)] if icon else [])
            + [ft.Text(text, size=12, weight=ft.FontWeight.W_600, color=INK)],
            spacing=6,
            tight=True,
        ),
        bgcolor="#E9EEEE",
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=8,
    )


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
        self.admin_screen = None
        self.content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=20)
        self.picker = ft.FilePicker()
        page.title = settings.name
        page.theme = ft.Theme(color_scheme_seed=ACCENT, use_material3=True)
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
        self.filters, self.query, self.status, self.offset = {}, "", "", 0
        self.page.appbar = None
        self.page.drawer = None
        self.page.controls.clear()
        identifier = ft.TextField(
            label="Usuario o correo",
            keyboard_type=ft.KeyboardType.TEXT,
            autofill_hints=ft.AutofillHint.USERNAME,
            max_length=254,
        )
        password = ft.TextField(
            label="Contraseña",
            password=True,
            can_reveal_password=True,
            autofill_hints=ft.AutofillHint.PASSWORD,
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
            ft.Icon(ft.Icons.ACCOUNT_BALANCE_OUTLINED, size=40, color=ACCENT),
            ft.Text(self.settings.name, size=30, weight=ft.FontWeight.BOLD, color=INK),
            ft.Text(INSTITUTION_NAME, size=16, color=INK),
            ft.Text("Cada solicitud, un recorrido claro.", size=17, color=MUTED),
            small("Piloto de gestión interna"),
            ft.Container(height=8),
            ft.Text(
                "Explora la mesa de partes" if is_demo else "Iniciar sesión",
                size=21,
                weight=ft.FontWeight.W_600,
            ),
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
            form.extend([identifier, password, small("Acceso para personal municipal autorizado.")])
        form.extend(
            [
                error,
                ft.FilledButton(
                    "Explorar demostración" if is_demo else "Ingresar",
                    icon=ft.Icons.ARROW_FORWARD,
                    on_click=enter,
                    width=360,
                    height=50,
                ),
            ]
        )
        card = panel(form, width=440)
        self.page.add(
            ft.SafeArea(
                ft.Container(
                    ft.Column(
                        [card, small("Mesa de partes · Expedientes · Trazabilidad")],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=24,
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
            title=ft.Text(self.settings.name, weight=ft.FontWeight.BOLD, color=INK),
            bgcolor="#FFFFFF",
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
        )
        nav_controls = [
            ft.Text("GESTIÓN MUNICIPAL", size=11, weight=ft.FontWeight.BOLD, color=MUTED),
            ft.Text(self.institution, size=19, weight=ft.FontWeight.W_600, color=INK),
            ft.Divider(color=LINE),
        ]
        nav_controls += [
            ft.TextButton(name, icon=icon, on_click=self.nav_handler(i), width=208, height=48)
            for i, (name, icon) in enumerate(navigation)
        ]
        nav_controls += [
            ft.Container(expand=True),
            ft.Divider(color=LINE),
            ft.Text(self.profile["display_name"], weight=ft.FontWeight.W_600, size=14),
            small(ROLES[self.profile["role"]]),
        ]
        self.sidebar = ft.Container(
            ft.Column(nav_controls, expand=True),
            width=244,
            padding=20,
            bgcolor="#FFFFFF",
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
        main.controls.append(
            ft.Container(
                self.content, expand=True, padding=ft.Padding.symmetric(horizontal=24, vertical=22)
            )
        )
        self.page.add(
            ft.SafeArea(
                ft.Row([self.sidebar, ft.Container(main, expand=True)], spacing=0, expand=True),
                expand=True,
            )
        )
        self.page.update()

    def heading(self, title, subtitle, actions=None):
        return ft.Column(
            [
                ft.Text(title, size=28, weight=ft.FontWeight.BOLD, color=INK),
                small(subtitle),
                ft.Row(actions or [], wrap=True, spacing=10),
            ],
            spacing=8,
        )

    async def navigate(self, index):
        if index == 3 and (not self.profile or self.profile["role"] != "admin"):
            raise UserError("Solo un administrador puede abrir Administración.")
        self.screen = index
        if self.page.drawer:
            self.page.drawer.selected_index = index
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
        for label, key, icon in [
            ("Expedientes", "total", ft.Icons.FOLDER_OPEN_OUTLINED),
            ("Pendientes", "pending", ft.Icons.SCHEDULE),
            ("Objetivo vencido", "overdue", ft.Icons.PRIORITY_HIGH),
            ("Atendidos", "resolved", ft.Icons.TASK_ALT),
        ]:
            stats.append(
                panel(
                    [
                        ft.Row(
                            [small(label), ft.Icon(icon, size=21, color=MUTED)],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(str(metrics[key]), size=34, weight=ft.FontWeight.BOLD, color=INK),
                    ],
                    col={"xs": 6, "md": 3},
                )
            )
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
            ft.Row([ft.Text("Actividad reciente", size=20, weight=ft.FontWeight.W_600)], wrap=True),
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
                ft.Icon(ft.Icons.INBOX_OUTLINED, size=36, color=MUTED),
                ft.Text(title, size=20, weight=ft.FontWeight.W_600),
                ft.Text(message, color=MUTED),
            ]
        )

    def open_handler(self, case_id):
        async def handler(_):
            await self.guard(lambda: self.detail(case_id))

        return handler

    def case_card(self, item):
        tags = [pill(STATUSES[item["status"]]), small(item["department"]["name"])]
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
                                color=ACCENT,
                            ),
                            small(timestamp(item["created_at"])),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    ),
                    ft.Text(item["title"], size=17, weight=ft.FontWeight.W_600, color=INK),
                    ft.Row(tags, wrap=True, spacing=10),
                    small(
                        f"Trámite: {(item.get('procedure_snapshot') or {}).get('name') or 'Sin trámite vinculado'}"
                    ),
                    small(
                        f"Responsable: {(item.get('assignee') or {}).get('display_name') or 'Pendiente de asignación'}"
                    ),
                    ft.Row(
                        [
                            small(f"Prioridad: {PRIORITIES[item['priority']]}"),
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
                spacing=12,
            ),
            bgcolor="#FFFFFF",
            border=ft.Border.all(1, LINE),
            border_radius=12,
            padding=20,
        )

    async def inbox(self):
        from munigest.work_ui import show_inbox

        await show_inbox(self)

    def new_case(self):
        if not self.can_register():
            self.notify("Tu perfil no puede registrar solicitudes.")
            return
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
                await self.detail(result["id"])

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
                    ft.Text("1. Solicitante", size=20, weight=ft.FontWeight.W_600),
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
                    ft.Text("2. Solicitud y destino", size=20, weight=ft.FontWeight.W_600),
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

    async def detail(self, case_id):
        from munigest.work_ui import work_event_lines, work_panel

        item, events, documents, areas = await asyncio.gather(
            self.repo.get_case(case_id),
            self.repo.events(case_id),
            self.repo.documents(case_id),
            self.repo.departments(include_inactive=True),
        )
        applicant = item["applicant"]
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
            ft.Text("Documentos", size=20, weight=ft.FontWeight.W_600),
            small("PDF, PNG o JPEG · máximo 10 MB por archivo"),
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
                    )
                ],
            ),
            ft.Row(
                [
                    pill(STATUSES[item["status"]]),
                    pill(PRIORITIES[item["priority"]]),
                    small(item["department"]["name"]),
                ],
                wrap=True,
            ),
            panel(
                [
                    ft.Text("Solicitud", size=20, weight=ft.FontWeight.W_600),
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
                        ft.Text("Registrar actuación", size=20, weight=ft.FontWeight.W_600),
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
                    ft.Text("Historial del expediente", size=20, weight=ft.FontWeight.W_600),
                    *timeline,
                ]
            )
        )
        self.page.update()

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
                    ft.Text("Áreas disponibles", size=20, weight=ft.FontWeight.W_600),
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
            ft.Text("Catálogo de trámites", size=20, weight=ft.FontWeight.W_600),
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
