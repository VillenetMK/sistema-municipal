"""Documentos del piloto generados en memoria, sin guardar datos en el servidor web."""

import io
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from munigest.domain import CHANNELS, PRIORITIES, STATUSES
from munigest.reports import filter_description, local_timestamp, report_summary

# Vera se distribuye con ReportLab: no depende de las fuentes instaladas en Windows.
_fonts = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("MuniRegular", str(_fonts / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("MuniBold", str(_fonts / "VeraBd.ttf")))
_glyphs = pdfmetrics.getFont("MuniRegular").face.charToGlyph
_PDF_LOCK = Lock()
INK = colors.HexColor("#192A32")
ACCENT = colors.HexColor("#164D48")
MUTED = colors.HexColor("#53616A")
LINE = colors.HexColor("#DCE2E4")
WIDTH = A4[0] - 40 * mm
STYLES = {
    "body": ParagraphStyle("body", fontName="MuniRegular", fontSize=9, leading=14, textColor=INK),
    "small": ParagraphStyle(
        "small", fontName="MuniRegular", fontSize=8, leading=12, textColor=MUTED
    ),
    "title": ParagraphStyle(
        "title", fontName="MuniBold", fontSize=22, leading=28, textColor=INK, spaceAfter=8
    ),
    "section": ParagraphStyle(
        "section",
        fontName="MuniBold",
        fontSize=12,
        leading=17,
        textColor=ACCENT,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True,
    ),
    "subject": ParagraphStyle(
        "subject",
        fontName="MuniBold",
        fontSize=11,
        leading=16,
        textColor=INK,
        spaceAfter=8,
    ),
    "label": ParagraphStyle("label", fontName="MuniBold", fontSize=8, leading=12, textColor=INK),
}


def _p(text, style="body"):
    # Todo texto de usuarios es literal: nunca se interpreta como etiquetas o enlaces.
    value = str(text if text is not None else "")
    value = "".join(c if ord(c) in _glyphs or c in "\n\t" else "?" for c in value)
    return Paragraph(escape(value).replace("\n", "<br/>"), STYLES[style])


def _table(rows, widths, *, header=False):
    data = [
        [_p(value, "label" if header and i == 0 else "body") for value in row]
        for i, row in enumerate(rows)
    ]
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9EEEE")))
    table.setStyle(TableStyle(style))
    return table


def _render(story, title, *, demo=False):
    stream = io.BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=23 * mm,
        bottomMargin=23 * mm,
        title=title,
        author="MuniGest Chiclayo",
        pageCompression=1,
    )

    def page(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(2)
        canvas.line(20 * mm, A4[1] - 16 * mm, A4[0] - 20 * mm, A4[1] - 16 * mm)
        canvas.setFont("MuniRegular", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            20 * mm,
            14 * mm,
            "DEMOSTRACIÓN - DATOS FICTICIOS"
            if demo
            else "MuniGest Chiclayo | Piloto de gestión interna",
        )
        canvas.drawRightString(A4[0] - 20 * mm, 14 * mm, f"Página {document.page}")
        canvas.restoreState()

    # ReportLab comparte registros de fuentes: serializar el armado entre sesiones.
    with _PDF_LOCK:
        doc.build(story, onFirstPage=page, onLaterPages=page)
    return stream.getvalue()


def receipt_pdf(receipt):
    item = receipt["case"]
    applicant = item["applicant"]
    story = [
        _p(receipt["institution_name"], "small"),
        Spacer(1, 8),
        _p("Constancia de registro", "title"),
        _p(item["reference"], "section"),
        _p(
            "Registro de una solicitud en el piloto de gestión interna. Conserve este código para su seguimiento."
        ),
        Spacer(1, 12),
        _table(
            [
                ["Fecha de registro (Chiclayo)", local_timestamp(item["created_at"])],
                ["Solicitante", applicant["full_name"]],
                [f"{applicant['document_type']} (parcial)", applicant["document_masked"]],
                ["Canal de ingreso", CHANNELS[item["channel"]]],
            ],
            [53 * mm, WIDTH - 53 * mm],
        ),
        _p("Solicitud registrada", "section"),
        _p(item["title"], "subject"),
        _p(item["description"]),
        _p("Situación al emitir esta copia", "section"),
        _table(
            [
                ["Estado actual", STATUSES[item["status"]]],
                ["Área actual", item["department_name"]],
                ["Trámite vinculado", item.get("procedure_name") or "Sin trámite vinculado"],
                ["Documentos adjuntos registrados", item["document_count"]],
                ["Versión del expediente", item["version"]],
            ],
            [53 * mm, WIDTH - 53 * mm],
        ),
        Spacer(1, 14),
        _p(f"Copia emitida: {local_timestamp(receipt['issued_at'])} (Chiclayo, UTC-5).", "small"),
        _p(
            "Esta copia acredita el registro en MuniGest. No es una resolución, una aprobación del trámite ni una constancia oficial del SGD municipal. No incorpora firma digital.",
            "small",
        ),
    ]
    return _render(story, f"Constancia {item['reference']}", demo=receipt.get("demo", False))


def summary_pdf(report):
    summary = report_summary(report)
    story = [
        _p(report["institution_name"], "small"),
        Spacer(1, 8),
        _p("Reporte de expedientes", "title"),
        _p(f"Corte: {local_timestamp(report['issued_at'])} (Chiclayo, UTC-5)", "small"),
        _p(f"Emitido por: {report['issued_by']}", "small"),
        _p(f"Alcance autorizado: {report['scope']}", "small"),
        _p("Filtros aplicados", "section"),
        *[_p(text) for text in filter_description(report)],
        _p("Resultados completos de la consulta", "section"),
        _table(
            [
                ["Indicador", "Expedientes"],
                ["Total de resultados", summary["total"]],
                ["Pendientes de atención", summary["pending"]],
                ["Pendientes con objetivo interno vencido", summary["overdue"]],
                ["Pendientes sin responsable", summary["unassigned"]],
            ],
            [WIDTH - 35 * mm, 35 * mm],
            header=True,
        ),
        _p("Distribución por estado", "section"),
        _table(
            [
                ["Estado", "Expedientes"],
                *[[STATUSES[key], value] for key, value in summary["statuses"].items()],
            ],
            [WIDTH - 35 * mm, 35 * mm],
            header=True,
        ),
        _p("Distribución por prioridad", "section"),
        _table(
            [
                ["Prioridad", "Expedientes"],
                *[[PRIORITIES[key], value] for key, value in summary["priorities"].items()],
            ],
            [WIDTH - 35 * mm, 35 * mm],
            header=True,
        ),
        _p("Distribución por área actual", "section"),
        _table(
            [["Área", "Expedientes"], *summary["departments"]]
            if summary["departments"]
            else [["Área", "Expedientes"], ["Sin resultados para estos filtros", 0]],
            [WIDTH - 35 * mm, 35 * mm],
            header=True,
        ),
        Spacer(1, 14),
        _p(
            "Los pendientes son los estados Recibido, En revisión y Observado. El objetivo interno vencido compara la fecha objetivo con el día del corte en Chiclayo; no representa un vencimiento legal. Las distribuciones incluyen todos los resultados autorizados. El detalle de cada expediente se descarga con CSV completo.",
            "small",
        ),
    ]
    return _render(story, "Reporte de expedientes - MuniGest", demo=report.get("demo", False))
