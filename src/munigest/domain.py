"""Reglas del flujo interno. Los plazos legales se configuran con el TUPA local."""

import csv
import io
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import PurePath
from uuid import UUID

STATUSES = {
    "recibido": "Recibido",
    "en_revision": "En revisión",
    "observado": "Observado",
    "atendido": "Atendido",
    "archivado": "Archivado",
}
TRANSITIONS = {
    "recibido": ("en_revision", "observado"),
    "en_revision": ("observado", "atendido"),
    "observado": ("en_revision",),
    "atendido": ("archivado",),
    "archivado": (),
}
ROLES = {
    "admin": "Administrador",
    "mesa_partes": "Mesa de partes",
    "gestor": "Gestor",
    "consulta": "Consulta",
}
PRIORITIES = {"normal": "Normal", "alta": "Alta", "urgente": "Urgente"}
CHANNELS = {"presencial": "Presencial", "virtual": "Virtual", "correo": "Correo"}
MAX_FILE_SIZE = 10 * 1024 * 1024
MUNICIPAL_TZ = timezone(timedelta(hours=-5))


class UserError(Exception):
    """Error seguro que puede presentarse al operador."""


class SessionExpired(UserError):
    pass


def clean_text(value, label, minimum=1, maximum=200):
    text = str(value or "").strip()
    if not minimum <= len(text) <= maximum or "\x00" in text:
        raise UserError(f"{label}: ingresa entre {minimum} y {maximum} caracteres.")
    return text


def municipal_today():
    return datetime.now(MUNICIPAL_TZ).date()


def optional_uuid(value, label):
    if value in (None, ""):
        return None
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError):
        raise UserError(f"Selecciona {label} válido.") from None


def optional_date(value, label):
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise UserError(f"{label}: usa una fecha válida con formato AAAA-MM-DD.") from None


def validate_case_work(raw):
    procedure = optional_uuid(raw.get("procedure_id"), "un trámite")
    if not procedure:
        raise UserError("Selecciona un trámite del catálogo.")
    if raw.get("priority") not in PRIORITIES:
        raise UserError("Selecciona una prioridad válida.")
    return {
        "procedure_id": procedure,
        "assigned_to": optional_uuid(raw.get("assigned_to"), "un responsable"),
        "priority": raw["priority"],
        "due_on": optional_date(raw.get("due_on"), "Fecha objetivo interna"),
        "note": clean_text(raw.get("note"), "Motivo", 10, 2000),
    }


def validate_draft(raw):
    data = dict(raw)
    data["title"] = clean_text(data.get("title"), "Asunto", 5, 160)
    data["description"] = clean_text(data.get("description"), "Descripción", 10, 5000)
    data["applicant_name"] = clean_text(data.get("applicant_name"), "Nombre o razón social", 3, 180)
    kind = data.get("document_type", "DNI")
    patterns = {
        "DNI": r"[0-9]{8}",
        "RUC": r"[0-9]{11}",
        "CE": r"[A-Za-z0-9]{9,12}",
        "PAS": r"[A-Za-z0-9]{6,15}",
    }
    data["document_number"] = str(data.get("document_number", "")).strip().upper()
    if kind not in patterns or not re.fullmatch(patterns[kind], data["document_number"]):
        raise UserError(
            "Revisa el tipo y número de documento: DNI 8 dígitos; RUC 11; CE 9–12; pasaporte 6–15."
        )
    data["document_type"] = kind
    for key in ("department_id", "request_id"):
        try:
            data[key] = str(UUID(data[key]))
        except (ValueError, TypeError, KeyError):
            raise UserError("Selecciona un área de destino válida.") from None
    if data.get("channel") not in CHANNELS or data.get("priority") not in PRIORITIES:
        raise UserError("Selecciona el canal de ingreso y la prioridad.")
    data["email"] = str(data.get("email") or "").strip()
    if data["email"] and (
        len(data["email"]) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", data["email"])
    ):
        raise UserError("Ingresa un correo válido o deja el campo vacío.")
    data["phone"] = str(data.get("phone") or "").strip()
    if data["phone"] and not re.fullmatch(r"\+?[0-9 ()-]{7,20}", data["phone"]):
        raise UserError("Revisa el teléfono de contacto.")
    data["due_on"] = optional_date(data.get("due_on"), "Fecha objetivo interna")
    data["procedure_id"] = optional_uuid(data.get("procedure_id"), "un trámite")
    data["assigned_to"] = optional_uuid(data.get("assigned_to"), "un responsable")
    return data


def validate_transition(current, target, note, same_department=True):
    note = clean_text(note, "Motivo o actuación", 10, 2000)
    if target == current:
        if same_department or current in {"atendido", "archivado"}:
            raise UserError("Elige un cambio de estado o un área de destino diferente.")
    elif target not in TRANSITIONS.get(current, ()):
        raise UserError("Ese cambio de estado no está permitido en el flujo de atención.")
    return note


def validate_attachment(name, data):
    if not data or len(data) > MAX_FILE_SIZE:
        raise UserError("El archivo debe contener datos y pesar como máximo 10 MB.")
    name = PurePath(name.replace("\\", "/")).name
    extension = PurePath(name).suffix.lower()
    signatures = {
        ".pdf": (b"%PDF-", "application/pdf"),
        ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
        ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
        ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    }
    if extension not in signatures or not data.startswith(signatures[extension][0]):
        raise UserError(
            "Adjunta un PDF, PNG o JPEG válido; cambiar la extensión no convierte el archivo."
        )
    return clean_text(name, "Nombre de archivo", 1, 180), signatures[extension][1]


def overdue(case, today=None):
    return bool(
        case.get("due_on")
        and case["status"] not in {"atendido", "archivado"}
        and date.fromisoformat(case["due_on"]) < (today or municipal_today())
    )


def safe_csv_cell(value):
    value = str(value or "")
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def export_cases(cases):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        [
            "Expediente",
            "Asunto",
            "Estado",
            "Área",
            "Trámite",
            "Responsable",
            "Prioridad",
            "Fecha de ingreso",
            "Fecha objetivo interna",
        ]
    )
    for item in cases:
        writer.writerow(
            [
                safe_csv_cell(x)
                for x in [
                    item["reference"],
                    item["title"],
                    STATUSES[item["status"]],
                    item.get("department", {}).get("name", ""),
                    (item.get("procedure_snapshot") or {}).get("name", ""),
                    (item.get("assignee") or {}).get("display_name", ""),
                    PRIORITIES[item["priority"]],
                    item["created_at"],
                    item.get("due_on", ""),
                ]
            ]
        )
    return stream.getvalue().encode("utf-8-sig")
