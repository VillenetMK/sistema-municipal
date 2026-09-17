"""Bandeja y organización del expediente. Se carga después de la interfaz principal."""

import asyncio

import flet as ft

from munigest.domain import PRIORITIES, STATUSES, UserError, export_cases
from munigest.ui import panel, small
from munigest.work_queue import CLOSED, DUE_FILTERS, eligible_workers, validate_filters


async def show_inbox(app):
    results, areas, procedures, staff = await asyncio.gather(
        app.repo.list_cases(app.query, app.status, app.offset, filters=app.filters),
        app.repo.departments(include_inactive=True),
        app.repo.procedures(include_inactive=True),
        app.repo.staff_directory(),
    )
    has_more = len(results) > 50
    app.rows = results[:50]
    filters = validate_filters(app.filters)
    search = ft.TextField(
        label="Buscar por código o asunto",
        value=app.query,
        max_length=60,
        prefix_icon=ft.Icons.SEARCH,
    )
    status = ft.Dropdown(
        label="Estado",
        value=app.status,
        options=[ft.DropdownOption("", "Todos los estados")]
        + [ft.DropdownOption(k, v) for k, v in STATUSES.items()],
    )

    def directory_options(rows, id_key, name_key):
        return [
            ft.DropdownOption(
                r[id_key], r[name_key] + (" (inactivo)" if not r["is_active"] else "")
            )
            for r in rows
        ]

    fields = {
        "department_id": ft.Dropdown(
            label="Área",
            value=filters["department_id"] or "",
            options=[ft.DropdownOption("", "Todas las áreas")]
            + directory_options(areas, "id", "name"),
        ),
        "procedure_id": ft.Dropdown(
            label="Trámite",
            value=filters["procedure_id"] or "",
            options=[ft.DropdownOption("", "Todos los trámites")]
            + directory_options(procedures, "id", "name"),
        ),
        "assignee": ft.Dropdown(
            label="Responsable",
            value=filters["assignee"],
            options=[
                ft.DropdownOption("", "Todos los responsables"),
                ft.DropdownOption("mine", "Asignados a mí"),
                ft.DropdownOption("unassigned", "Sin responsable"),
            ]
            + directory_options(staff, "user_id", "display_name"),
        ),
        "priority": ft.Dropdown(
            label="Prioridad",
            value=filters["priority"],
            options=[ft.DropdownOption("", "Todas las prioridades")]
            + [ft.DropdownOption(k, v) for k, v in PRIORITIES.items()],
        ),
        "due": ft.Dropdown(
            label="Fecha objetivo interna",
            value=filters["due"],
            options=[ft.DropdownOption(k, v) for k, v in DUE_FILTERS.items()],
        ),
        "received_from": ft.TextField(
            label="Ingreso desde",
            value=filters["received_from"] or "",
            hint_text="AAAA-MM-DD",
            max_length=10,
        ),
        "received_to": ft.TextField(
            label="Ingreso hasta",
            value=filters["received_to"] or "",
            hint_text="AAAA-MM-DD",
            max_length=10,
        ),
        "pending_only": ft.Checkbox(label="Solo pendientes", value=filters["pending_only"]),
    }

    async def apply_filter(e):
        async def work():
            app.filters = validate_filters({k: f.value for k, f in fields.items()})
            app.query, app.status, app.offset = search.value or "", status.value or "", 0
            await app.navigate(1)

        await app.guard(work, e.control)

    def preset(values):
        async def handler(e):
            app.filters, app.query, app.status, app.offset = values.copy(), "", "", 0
            await app.guard(lambda: app.navigate(1), e.control)

        return handler

    def page_handler(direction):
        async def handler(e):
            app.offset = max(0, app.offset + direction * 50)
            await app.guard(lambda: app.navigate(1), e.control)

        return handler

    async def export(e):
        async def work():
            await app.picker.save_file(
                file_name="expedientes_pagina.csv", src_bytes=export_cases(app.rows)
            )

        await app.guard(work, e.control)

    search.on_submit = apply_filter
    for field in [status, *fields.values()]:
        field.col = {"xs": 12, "md": 6, "xl": 3}
    actions = (
        [ft.FilledButton("Registrar solicitud", icon=ft.Icons.ADD, on_click=app.new_handler)]
        if app.can_register()
        else []
    )
    actions.append(
        ft.OutlinedButton(
            "Exportar página CSV", icon=ft.Icons.DOWNLOAD, disabled=not app.rows, on_click=export
        )
    )
    app.content.controls = [
        app.heading(
            "Bandeja de expedientes",
            "Organiza las solicitudes por trámite, responsable y fecha objetivo interna.",
            actions,
        ),
        ft.Row(
            [
                ft.OutlinedButton(
                    "Mis pendientes",
                    icon=ft.Icons.PERSON_OUTLINED,
                    on_click=preset({"assignee": "mine", "pending_only": True}),
                ),
                ft.OutlinedButton(
                    "Sin responsable",
                    on_click=preset({"assignee": "unassigned", "pending_only": True}),
                ),
                ft.OutlinedButton("Objetivo hoy", on_click=preset({"due": "today"})),
                ft.TextButton("Limpiar filtros", on_click=preset({})),
            ],
            wrap=True,
        ),
        panel(
            [
                search,
                ft.ResponsiveRow([status, *fields.values()], run_spacing=14),
                ft.FilledButton(
                    "Aplicar filtros", icon=ft.Icons.FILTER_LIST, on_click=apply_filter
                ),
                small(
                    "Las fechas de ingreso incluyen el día completo en horario de Chiclayo. "
                    "Los objetivos son internos y no representan plazos legales."
                ),
            ]
        ),
        ft.Row(
            [
                small(f"Página {app.offset // 50 + 1} · {len(app.rows)} expedientes"),
                ft.TextButton("Anterior", disabled=app.offset == 0, on_click=page_handler(-1)),
                ft.TextButton("Siguiente", disabled=not has_more, on_click=page_handler(1)),
            ],
            wrap=True,
        ),
        *(
            [app.case_card(x) for x in app.rows]
            or [app.empty("No hay resultados", "Revisa los filtros o usa Limpiar filtros.")]
        ),
    ]


async def work_panel(app, item):
    ficha = item.get("procedure_snapshot") or {}
    assignee = item.get("assignee") or {}
    controls = [
        ft.Text("Organización del expediente", size=20, weight=ft.FontWeight.W_600),
        ft.Text(f"Trámite: {ficha.get('name') or 'Sin trámite vinculado'}"),
        small(f"Responsable: {assignee.get('display_name') or 'Pendiente de asignación'}"),
        small(
            f"Prioridad: {PRIORITIES[item['priority']]} · Objetivo interno: {item.get('due_on') or 'Sin fecha'}"
        ),
    ]
    if ficha:
        controls.extend(
            [
                small(
                    f"Ficha {ficha['code']} · versión {ficha.get('version', 1)} conservada al vincularla"
                ),
                ft.Text(ficha.get("requirements") or "Sin requisitos registrados en la ficha."),
                small(ficha.get("legal_basis") or "Ficha de referencia general."),
            ]
        )
    if app.profile["role"] == "consulta" or item["status"] in CLOSED:
        return panel(controls)
    procedures, staff = await asyncio.gather(app.repo.procedures(), app.repo.staff_directory())
    options = [ft.DropdownOption(p["id"], p["name"]) for p in procedures]
    if item.get("procedure_id") and not any(p["id"] == item["procedure_id"] for p in procedures):
        options.append(
            ft.DropdownOption(
                item["procedure_id"], (ficha.get("name") or "Ficha anterior") + " (conservada)"
            )
        )
    workers = eligible_workers(staff, item["department_id"])
    assignee_options = [ft.DropdownOption("", "Pendiente de asignación")]
    assignee_options.extend(ft.DropdownOption(s["user_id"], s["display_name"]) for s in workers)
    if item.get("assigned_to") and not any(s["user_id"] == item["assigned_to"] for s in workers):
        assignee_options.append(
            ft.DropdownOption(
                item["assigned_to"],
                (assignee.get("display_name") or "Responsable anterior") + " (revisar asignación)",
            )
        )
    fields = {
        "procedure_id": ft.Dropdown(
            label="Trámite del expediente", value=item.get("procedure_id"), options=options
        ),
        "assigned_to": ft.Dropdown(
            label="Responsable del área",
            value=item.get("assigned_to") or "",
            options=assignee_options,
        ),
        "priority": ft.Dropdown(
            label="Prioridad",
            value=item["priority"],
            options=[ft.DropdownOption(k, v) for k, v in PRIORITIES.items()],
        ),
        "due_on": ft.TextField(
            label="Fecha objetivo interna",
            value=item.get("due_on") or "",
            hint_text="AAAA-MM-DD",
            max_length=10,
        ),
    }
    note = ft.TextField(
        label="Motivo de la organización", multiline=True, min_lines=2, max_lines=4, max_length=2000
    )
    error = ft.Text("", color="#7B2222", visible=False)

    async def save(e):
        async def work():
            error.visible = False
            try:
                await app.repo.set_case_work(
                    item, {**{k: f.value for k, f in fields.items()}, "note": note.value}
                )
            except UserError as exc:
                error.value, error.visible = str(exc), True
                return
            await app.detail(item["id"])
            app.notify("Organización guardada en el historial del expediente.")

        await app.guard(work, e.control)

    for field in fields.values():
        field.col = {"xs": 12, "md": 6}
    controls.extend(
        [
            ft.Divider(),
            small(
                "El responsable pertenece al área actual. Al derivar, la nueva área asignará a su encargado."
            ),
            ft.ResponsiveRow(list(fields.values()), run_spacing=14),
            note,
            error,
            ft.FilledButton("Guardar organización", icon=ft.Icons.SAVE_OUTLINED, on_click=save),
        ]
    )
    return panel(controls)


def work_event_lines(event):
    after = event.get("work_after")
    if not after:
        return []
    before = event.get("work_before") or {}
    descriptions = [
        ("Responsable", before.get("assignee_name"), after.get("assignee_name"), "Sin responsable"),
        (
            "Trámite",
            (before.get("procedure_snapshot") or {}).get("name"),
            (after.get("procedure_snapshot") or {}).get("name"),
            "Sin trámite",
        ),
        (
            "Prioridad",
            PRIORITIES.get(before.get("priority")),
            PRIORITIES.get(after.get("priority")),
            "Sin definir",
        ),
        ("Objetivo interno", before.get("due_on"), after.get("due_on"), "Sin fecha"),
    ]
    return [
        small(f"{label}: {old or empty} → {new or empty}")
        for label, old, new, empty in descriptions
        if old != new
    ]
