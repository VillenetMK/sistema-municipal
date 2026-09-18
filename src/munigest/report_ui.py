"""Descargas que vuelven a verificar el acceso y obtienen una consulta completa."""

import asyncio
from copy import deepcopy

import flet as ft

from munigest.pdf_exports import receipt_pdf, summary_pdf
from munigest.reports import filter_description, local_timestamp, report_csv, report_summary
from munigest.ui import panel, small


async def download_receipt(app, case_id, control):
    async def work():
        receipt = await app.repo.case_receipt(case_id)
        content = await asyncio.to_thread(receipt_pdf, receipt)
        await app.picker.save_file(
            file_name=f"constancia_{receipt['case']['reference']}.pdf", src_bytes=content
        )

    await app.guard(work, control)


async def show_report(app):
    # Los campos aún no aplicados de la bandeja no alteran los filtros del reporte.
    query, status, filters = app.query, app.status, deepcopy(app.filters)

    async def load():
        report = await app.repo.case_report(query, status, filters=filters)
        render(report)
        app.page.update()
        return report

    async def refresh(e):
        await app.guard(load, e.control)

    def download(format_name):
        async def handler(e):
            async def work():
                # Cada descarga comprueba nuevamente sesión, perfil y RLS en el servidor.
                report = await load()
                builder = report_csv if format_name == "csv" else summary_pdf
                content = await asyncio.to_thread(builder, report)
                prefix = "expedientes" if format_name == "csv" else "resumen_expedientes"
                await app.picker.save_file(
                    file_name=f"{prefix}_{report['local_date']}.{format_name}", src_bytes=content
                )

            await app.guard(work, e.control)

        return handler

    def render(report):
        summary = report_summary(report)
        app.content.controls = [
            app.heading(
                "Reportes de expedientes",
                "La consulta incluye todos los resultados de los filtros aplicados.",
                [
                    ft.TextButton(
                        "Volver a la bandeja", icon=ft.Icons.ARROW_BACK, on_click=app.nav_handler(1)
                    )
                ],
            ),
            panel(
                [
                    ft.Text("Consulta seleccionada", size=20, weight=ft.FontWeight.W_600),
                    small(f"Alcance: {report['scope']}"),
                    *[ft.Text(text) for text in filter_description(report)],
                    small(f"Corte: {local_timestamp(report['issued_at'])} · Chiclayo (UTC-5)"),
                    ft.OutlinedButton(
                        "Actualizar reporte", icon=ft.Icons.REFRESH, on_click=refresh
                    ),
                ]
            ),
            ft.ResponsiveRow(
                [
                    panel(
                        [
                            ft.Text(str(summary[key]), size=30, weight=ft.FontWeight.BOLD),
                            ft.Text(label),
                        ],
                        col={"xs": 12, "md": 6, "xl": 3},
                    )
                    for key, label in [
                        ("total", "Resultados"),
                        ("pending", "Pendientes"),
                        ("overdue", "Objetivo interno vencido"),
                        ("unassigned", "Pendientes sin responsable"),
                    ]
                ]
            ),
            panel(
                [
                    ft.Text("Descargar resultados", size=20, weight=ft.FontWeight.W_600),
                    ft.Text(
                        "CSV completo incluye una fila por expediente y puede abrirse en Excel. Resumen PDF contiene los indicadores y su distribución por estado, prioridad y área."
                    ),
                    ft.Row(
                        [
                            ft.FilledButton(
                                "CSV completo", icon=ft.Icons.DOWNLOAD, on_click=download("csv")
                            ),
                            ft.OutlinedButton(
                                "Resumen PDF",
                                icon=ft.Icons.PICTURE_AS_PDF,
                                on_click=download("pdf"),
                            ),
                        ],
                        wrap=True,
                    ),
                    small(
                        "Cada descarga actualiza el corte. Se admiten hasta 10000 resultados por consulta; si se supera ese límite, reduce el período o aplica más filtros."
                    ),
                    small(
                        "El reporte omite documentos de identidad y datos de contacto. El asunto conserva el texto registrado. Los objetivos son internos y no representan plazos legales."
                    ),
                ]
            ),
        ]

    await load()
