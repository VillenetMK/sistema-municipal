"""Filtros de bandeja y fechas internas compartidos por Supabase y demostración."""

from datetime import datetime, time, timedelta

from munigest.domain import (
    MUNICIPAL_TZ,
    PRIORITIES,
    UserError,
    municipal_today,
    optional_date,
    optional_uuid,
)

DUE_FILTERS = {
    "": "Todas las fechas objetivo",
    "overdue": "Objetivo vencido",
    "today": "Objetivo hoy",
    "soon": "Objetivo en próximos 3 días",
    "none": "Sin fecha objetivo",
}
CLOSED = {"atendido", "archivado"}


def validate_filters(raw=None):
    raw = raw or {}
    assignee = raw.get("assignee") or ""
    if assignee not in {"", "mine", "unassigned"}:
        assignee = optional_uuid(assignee, "un responsable")
    result = {
        "department_id": optional_uuid(raw.get("department_id"), "un área"),
        "procedure_id": optional_uuid(raw.get("procedure_id"), "un trámite"),
        "assignee": assignee,
        "priority": raw.get("priority") or "",
        "due": raw.get("due") or "",
        "pending_only": raw.get("pending_only", False),
        "received_from": optional_date(raw.get("received_from"), "Ingreso desde"),
        "received_to": optional_date(raw.get("received_to"), "Ingreso hasta"),
    }
    if result["priority"] not in {"", *PRIORITIES} or result["due"] not in DUE_FILTERS:
        raise UserError("Revisa los filtros de prioridad y fecha objetivo.")
    if type(result["pending_only"]) is not bool:
        raise UserError("Indica si deseas ver solamente pendientes.")
    if (
        result["received_from"]
        and result["received_to"]
        and result["received_from"] > result["received_to"]
    ):
        raise UserError("La fecha de ingreso inicial no puede ser posterior a la final.")
    if result["received_to"] == "9999-12-31":
        raise UserError("La fecha de ingreso final excede el rango admitido.")
    return result


def rest_filters(raw, user_id, today=None):
    filters = validate_filters(raw)
    today = today or municipal_today()
    conditions = []
    for key in ("department_id", "procedure_id", "priority"):
        if filters[key]:
            conditions.append(f"{key}.eq.{filters[key]}")
    assignee = filters["assignee"]
    if assignee == "mine":
        assignee = optional_uuid(user_id, "un usuario con sesión activa")
        if not assignee:
            raise UserError("Inicia sesión para consultar tus pendientes.")
    if assignee == "unassigned":
        conditions.append("assigned_to.is.null")
    elif assignee:
        conditions.append(f"assigned_to.eq.{assignee}")
    if filters["pending_only"] or filters["due"] in {"overdue", "today", "soon"}:
        conditions.append("status.not.in.(atendido,archivado)")
    due = filters["due"]
    if due == "overdue":
        conditions.append(f"due_on.lt.{today}")
    elif due == "today":
        conditions.append(f"due_on.eq.{today}")
    elif due == "soon":
        conditions.extend([f"due_on.gt.{today}", f"due_on.lte.{today + timedelta(days=3)}"])
    elif due == "none":
        conditions.append("due_on.is.null")
    for field, op in [("received_from", "gte"), ("received_to", "lt")]:
        if filters[field]:
            day = datetime.fromisoformat(filters[field]).date()
            if field == "received_to":
                day += timedelta(days=1)
            boundary = datetime.combine(day, time(), MUNICIPAL_TZ).isoformat()
            conditions.append(f"created_at.{op}.{boundary}")
    return {"and": "(" + ",".join(conditions) + ")"} if conditions else {}


def matches_filters(item, raw, user_id, today=None):
    filters = validate_filters(raw)
    today = today or municipal_today()
    for key in ("department_id", "procedure_id", "priority"):
        if filters[key] and item.get(key) != filters[key]:
            return False
    assignee = user_id if filters["assignee"] == "mine" else filters["assignee"]
    if assignee == "unassigned" and item.get("assigned_to"):
        return False
    if assignee and assignee != "unassigned" and item.get("assigned_to") != assignee:
        return False
    if (filters["pending_only"] or filters["due"] in {"overdue", "today", "soon"}) and item[
        "status"
    ] in CLOSED:
        return False
    due = item.get("due_on")
    comparisons = {
        "overdue": bool(due and due < str(today)),
        "today": due == str(today),
        "soon": bool(due and str(today) < due <= str(today + timedelta(days=3))),
        "none": not due,
    }
    if filters["due"] and not comparisons[filters["due"]]:
        return False
    received = (
        datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
        .astimezone(MUNICIPAL_TZ)
        .date()
        .isoformat()
    )
    return not (
        (filters["received_from"] and received < filters["received_from"])
        or (filters["received_to"] and received > filters["received_to"])
    )


def due_notice(item, today=None):
    if item["status"] in CLOSED or not item.get("due_on"):
        return ""
    today = today or municipal_today()
    due = item["due_on"]
    if due < str(today):
        return "Objetivo vencido"
    if due == str(today):
        return "Objetivo hoy"
    if due <= str(today + timedelta(days=3)):
        return "Objetivo en próximos 3 días"
    return ""


def eligible_workers(staff, department_id):
    return [
        s
        for s in staff
        if s["is_active"]
        and s["role"] in {"admin", "mesa_partes", "gestor"}
        and s.get("department_id") == department_id
    ]
