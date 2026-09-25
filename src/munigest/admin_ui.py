"""Administración de catálogos y perfiles, exclusiva de administradores activos."""

import asyncio
from uuid import uuid4

import flet as ft

from munigest.administration import ENTITIES
from munigest.design import ACCENT, INK, SOFT
from munigest.domain import ROLES, UserError
from munigest.institution import UNIT_TYPES

# Este módulo se carga desde navigate(), cuando la interfaz base ya está definida.
from munigest.ui import panel, pill, small, timestamp

FIELD_LABELS = {
    "code": "Código",
    "name": "Nombre",
    "display_name": "Nombre",
    "is_active": "Estado",
    "unit_type": "Tipo de área",
    "source_url": "Fuente",
    "department_id": "Área",
    "role": "Rol",
    "requirements": "Requisitos",
    "is_official": "Sustento oficial",
    "legal_basis": "Sustento",
    "fee_pen": "Importe",
    "deadline_days": "Plazo",
}


class AdministrationScreen:
    def __init__(self, app):
        self.app = app
        self.entity = "departments"
        self.query = ""
        self.offset = 0

    def require_admin(self):
        if not self.app.profile or self.app.profile["role"] != "admin":
            raise UserError("Solo un administrador puede abrir Administración.")

    def switch_handler(self, entity):
        async def handler(_):
            self.entity, self.query, self.offset = entity, "", 0
            await self.app.guard(self.show)

        return handler

    def edit_handler(self, record=None):
        async def handler(_):
            await self.app.guard(lambda: self.editor(record))

        return handler

    async def show(self):
        self.require_admin()
        rows = await self.app.repo.admin_records(self.entity, self.query, self.offset)
        query = ft.TextField(label="Buscar por nombre o código", value=self.query, max_length=100)

        async def search(_):
            self.query, self.offset = query.value or "", 0
            await self.app.guard(self.show)

        async def previous(_):
            self.offset = max(0, self.offset - 50)
            await self.app.guard(self.show)

        async def next_page(_):
            self.offset += 50
            await self.app.guard(self.show)

        query.on_submit = search
        actions = [
            ft.OutlinedButton(
                label,
                on_click=self.switch_handler(entity),
                tooltip="Sección actual",
                style=ft.ButtonStyle(
                    bgcolor=SOFT,
                    color=INK,
                    side=ft.BorderSide(2, ACCENT),
                ),
            )
            if entity == self.entity
            else ft.TextButton(label, on_click=self.switch_handler(entity))
            for entity, label in ENTITIES.items()
        ]
        controls = [
            self.app.heading(
                "Administración",
                "Organiza las áreas, el catálogo y los accesos del equipo.",
                actions,
            ),
            panel(
                [
                    ft.Text(ENTITIES[self.entity], size=22, weight=ft.FontWeight.BOLD),
                    small(
                        "Incluye registros activos e inactivos. Cada cambio conserva su historial."
                    ),
                    query,
                    ft.Row(
                        [
                            ft.OutlinedButton("Buscar", icon=ft.Icons.SEARCH, on_click=search),
                            *(
                                [
                                    ft.FilledButton(
                                        "Crear área"
                                        if self.entity == "departments"
                                        else "Crear trámite",
                                        icon=ft.Icons.ADD,
                                        on_click=self.edit_handler(),
                                    )
                                ]
                                if self.entity != "staff_profiles"
                                else []
                            ),
                        ],
                        wrap=True,
                    ),
                ]
            ),
        ]
        if self.entity == "staff_profiles":
            from munigest.account_ui import AccountScreen

            accounts = AccountScreen(self.app)

            async def invitations(_):
                await self.app.guard(accounts.show_invitations)

            controls.append(
                panel(
                    [
                        ft.Text("Permisos del equipo", weight=ft.FontWeight.BOLD),
                        small(
                            "Administrador: acceso global y configuración. Mesa de partes: recepción y gestión global. "
                            "Gestor: atención de su área. Consulta: lectura de su área."
                        ),
                        small(
                            "Crea invitaciones con correo, rol y área. Cada persona confirma su correo y elige su contraseña."
                        ),
                        ft.FilledButton(
                            "Usuarios e invitaciones",
                            on_click=invitations,
                            disabled=self.app.settings.mode == "demo",
                        ),
                    ]
                )
            )
        for row in rows[:50]:
            title = row.get("name") or row["display_name"]
            subtitle = ROLES[row["role"]] if self.entity == "staff_profiles" else row["code"]
            controls.append(
                panel(
                    [
                        ft.Text(title, size=18, weight=ft.FontWeight.W_600),
                        small(subtitle),
                        ft.Row(
                            [
                                pill("Activo" if row["is_active"] else "Inactivo"),
                                ft.TextButton(
                                    "Editar e historial",
                                    icon=ft.Icons.EDIT_OUTLINED,
                                    on_click=self.edit_handler(row),
                                ),
                            ],
                            wrap=True,
                        ),
                    ]
                )
            )
        if not rows:
            controls.append(
                panel(
                    [
                        ft.Text("No se encontraron registros."),
                        small("Prueba con otro nombre o código."),
                    ]
                )
            )
        controls.append(
            ft.Row(
                [
                    ft.TextButton("Anterior", disabled=self.offset == 0, on_click=previous),
                    small(f"Página {self.offset // 50 + 1}"),
                    ft.TextButton("Siguiente", disabled=len(rows) <= 50, on_click=next_page),
                ],
                wrap=True,
            )
        )
        self.app.content.controls = controls
        self.app.page.update()

    async def editor(self, record=None):
        self.require_admin()
        entity = self.entity
        if entity == "staff_profiles" and record is None:
            raise UserError("Selecciona una cuenta existente.")
        key = "user_id" if entity == "staff_profiles" else "id"
        record = dict(record or {key: str(uuid4()), "version": 0, "is_active": True})
        areas, history = await asyncio.gather(
            self.app.repo.departments(), self.app.repo.admin_history(entity, record[key])
        )
        fields = {}

        def text_field(key, label, maximum, multiline=False):
            fields[key] = ft.TextField(
                label=label,
                value=str(record.get(key) if record.get(key) is not None else ""),
                max_length=maximum,
                multiline=multiline,
                min_lines=3 if multiline else 1,
                max_lines=6 if multiline else 1,
            )

        if entity == "staff_profiles":
            text_field("display_name", "Nombre del usuario", 120)
            fields["role"] = ft.Dropdown(
                label="Rol",
                value=record.get("role"),
                options=[ft.DropdownOption(k, v) for k, v in ROLES.items()],
            )
        else:
            text_field("code", "Código interno", 20)
            text_field("name", "Nombre", 120)
        if entity == "departments":
            fields["unit_type"] = ft.Dropdown(
                label="Tipo de área",
                value=record.get("unit_type", "referencia"),
                options=[ft.DropdownOption(k, v) for k, v in UNIT_TYPES.items()],
            )
            text_field("source_url", "Enlace de referencia (opcional, HTTPS)", 1000)
        else:
            options = [ft.DropdownOption("", "Sin área asignada")]
            options.extend(ft.DropdownOption(d["id"], d["name"]) for d in areas)
            if record.get("department_id") and not any(
                d["id"] == record["department_id"] for d in areas
            ):
                options.append(
                    ft.DropdownOption(
                        record["department_id"], "Área inactiva: selecciona otra para activar"
                    )
                )
            fields["department_id"] = ft.Dropdown(
                label="Área asignada", value=record.get("department_id") or "", options=options
            )
        if entity == "procedures":
            text_field("requirements", "Requisitos de la ficha", 5000, multiline=True)
            text_field(
                "legal_basis", "Sustento normativo y referencia de la fuente", 2000, multiline=True
            )
            fields["is_official"] = ft.Checkbox(
                label="Ficha contrastada con la fuente oficial",
                value=record.get("is_official", False),
            )
            text_field("fee_pen", "Importe en soles (opcional)", 13)
            text_field("deadline_days", "Plazo de la ficha en días (opcional)", 4)
        fields["is_active"] = ft.Checkbox(label="Registro activo", value=record["is_active"])
        own_profile = entity == "staff_profiles" and record[key] == self.app.profile["user_id"]
        if own_profile:
            fields["role"].disabled = True
            fields["is_active"].disabled = True
        reason = ft.TextField(
            label="Motivo del cambio",
            hint_text="Explica qué se crea o actualiza y por qué.",
            max_length=500,
            multiline=True,
            min_lines=2,
            max_lines=4,
        )
        error = ft.Text("", color="#7B2222", visible=False)

        async def back(_):
            await self.app.guard(self.show)

        async def save(e):
            async def work():
                error.visible = False
                try:
                    result = await self.app.repo.admin_save(
                        entity,
                        {key: record[key], **{k: f.value for k, f in fields.items()}},
                        record["version"],
                        reason.value,
                    )
                except UserError as exc:
                    error.value, error.visible = str(exc), True
                    return
                # Conservar la versión confirmada aunque falle una lectura posterior.
                record.update(result)
                reason.value = ""
                if own_profile:
                    self.app.profile = result
                    self.app.repo.profile = result
                    self.app.shell()
                self.app.departments = await self.app.repo.departments()
                await self.editor(result)
                self.app.notify("Cambio guardado. El historial ya está actualizado.")

            await self.app.guard(work, e.control)

        for field in fields.values():
            field.col = {"xs": 12, "md": 6}
        for name in ("requirements", "legal_basis"):
            if name in fields:
                fields[name].col = 12
        description = "Los cambios se aplican al guardar y quedan registrados con tu nombre."
        controls = [
            self.app.heading(
                "Editar registro" if record["version"] else "Nuevo registro",
                description,
                [ft.TextButton("Volver a la lista", icon=ft.Icons.ARROW_BACK, on_click=back)],
            ),
        ]
        if entity == "procedures":
            controls.append(
                panel(
                    [
                        small(
                            "Esta ficha orienta la atención. El importe y el plazo no se cobran ni se "
                            "aplican automáticamente a los expedientes. Deja vacíos los datos sin confirmar."
                        )
                    ]
                )
            )
        if entity == "staff_profiles":
            controls.append(
                panel(
                    [
                        small(
                            "La desactivación bloquea nuevas operaciones de la cuenta. "
                            "Cambiar de área también cambia los expedientes que puede consultar."
                        ),
                        small("Tu propia cuenta conserva el rol Administrador y el acceso activo."),
                    ]
                )
            )
        controls.append(
            panel(
                [
                    ft.ResponsiveRow(list(fields.values()), run_spacing=16),
                    reason,
                    error,
                    ft.FilledButton("Guardar cambios", icon=ft.Icons.SAVE_OUTLINED, on_click=save),
                ]
            )
        )
        entries = []
        for event in history:
            before, after = event.get("before_data") or {}, event["after_data"]
            changed = [
                label for key, label in FIELD_LABELS.items() if before.get(key) != after.get(key)
            ]
            entries.append(
                ft.Column(
                    [
                        ft.Text(
                            f"{timestamp(event['created_at'])} · {event['actor_name']}",
                            weight=ft.FontWeight.W_600,
                        ),
                        ft.Text(event["reason"]),
                        small(
                            "Alta del registro"
                            if not before
                            else "Campos: " + (", ".join(changed) or "Sin cambios de contenido")
                        ),
                        ft.Divider(),
                    ]
                )
            )
        controls.append(
            panel(
                [
                    ft.Text("Historial de Administración", size=20, weight=ft.FontWeight.W_600),
                    small("Últimos 25 cambios. Se conservan las versiones anteriores."),
                    *(entries or [small("Aún no hay cambios registrados desde Administración.")]),
                ]
            )
        )
        self.app.content.controls = controls
        self.app.page.update()
