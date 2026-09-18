"""Reportes sobre una consulta completa, con la fecha y el alcance del servidor."""

import csv
import io
import re
from collections import Counter
from datetime import datetime

from munigest.domain import CHANNELS, MUNICIPAL_TZ, PRIORITIES, STATUSES, UserError, safe_csv_cell
from munigest.work_queue import CLOSED, DUE_FILTERS, validate_filters

MAX_REPORT_ROWS = 10_000
REPORT_LIMIT_MESSAGE = (
    "La consulta supera 10000 expedientes. Reduce el período o aplica más filtros."
)


def search_term(query):
    return re.sub(r"[^0-9A-Za-zÀ-ÿ -]", " ", query or "").strip()[:60]


def report_filters(query="", status="", filters=None):
    if status not in {"", *STATUSES}:
        raise UserError("Selecciona un estado válido para el reporte.")
    return {**validate_filters(filters), "query": search_term(query), "status": status}


def local_timestamp(value):
    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(MUNICIPAL_TZ)
        .strftime("%d/%m/%Y %H:%M:%S")
    )


def filter_description(report):
    values = report["filters"]
    labels = report.get("filter_labels", {})
    parts = []
    if values["query"]:
        parts.append(f"Búsqueda: {values['query']}")
    if values["status"]:
        parts.append(f"Estado: {STATUSES[values['status']]}")
    for key, title in [("department_id", "Área"), ("procedure_id", "Trámite")]:
        if values[key]:
            parts.append(f"{title}: {labels.get(key) or values[key]}")
    if values["assignee"]:
        name = {"mine": "Asignados a mí", "unassigned": "Sin responsable"}.get(
            values["assignee"], labels.get("assignee") or values["assignee"]
        )
        parts.append(f"Responsable: {name}")
    if values["priority"]:
        parts.append(f"Prioridad: {PRIORITIES[values['priority']]}")
    if values["due"]:
        parts.append(DUE_FILTERS[values["due"]])
    if values["pending_only"]:
        parts.append("Solo pendientes")
    if values["received_from"]:
        parts.append(f"Ingreso desde: {values['received_from']}")
    if values["received_to"]:
        parts.append(f"Ingreso hasta: {values['received_to']}")
    return parts or ["Todos los expedientes permitidos por tu perfil"]


def report_summary(report):
    rows = report["rows"]
    today = report["local_date"]
    pending = [row for row in rows if row["status"] not in CLOSED]
    return {
        "total": len(rows),
        "pending": len(pending),
        "overdue": sum(bool(r.get("due_on") and r["due_on"] < today) for r in pending),
        "unassigned": sum(not r.get("assigned_to") for r in pending),
        "statuses": {key: sum(r["status"] == key for r in rows) for key in STATUSES},
        "priorities": {key: sum(r["priority"] == key for r in rows) for key in PRIORITIES},
        "departments": sorted(Counter(r["department_name"] for r in rows).items()),
    }


def report_csv(report):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "Expediente",
            "Asunto",
            "Estado",
            "Área actual",
            "Trámite vinculado",
            "Responsable",
            "Prioridad",
            "Canal",
            "Ingreso (Chiclayo)",
            "Fecha objetivo interna",
            "Versión",
            "Corte del reporte (Chiclayo)",
        ]
    )
    for row in report["rows"]:
        writer.writerow(
            safe_csv_cell(value)
            for value in [
                row["reference"],
                row["title"],
                STATUSES[row["status"]],
                row["department_name"],
                row.get("procedure_name") or "Sin trámite vinculado",
                row.get("assignee_name") or "Sin responsable",
                PRIORITIES[row["priority"]],
                CHANNELS[row["channel"]],
                local_timestamp(row["created_at"]),
                row.get("due_on") or "",
                row["version"],
                local_timestamp(report["issued_at"]),
            ]
        )
    return output.getvalue().encode("utf-8-sig")
