"""Validaciones de Administración; la base vuelve a comprobar permisos y reglas."""

import re
from decimal import Decimal, InvalidOperation
from uuid import UUID

from munigest.domain import ROLES, UserError, clean_text
from munigest.institution import UNIT_TYPES

ENTITIES = {"departments": "Áreas", "procedures": "Trámites", "staff_profiles": "Personal"}


def validate_admin_record(entity, raw):
    if entity not in ENTITIES:
        raise UserError("Selecciona una sección de Administración.")
    data = dict(raw)
    key = "user_id" if entity == "staff_profiles" else "id"
    try:
        data[key] = str(UUID(str(data[key])))
        data["department_id"] = (
            str(UUID(str(data["department_id"]))) if data.get("department_id") else None
        )
    except (ValueError, KeyError, TypeError):
        raise UserError("El identificador o el área seleccionada no son válidos.") from None
    if type(data.get("is_active")) is not bool:
        raise UserError("Indica si el registro está activo.")
    if entity == "staff_profiles":
        data["display_name"] = clean_text(data.get("display_name"), "Nombre", 3, 120)
        if data.get("role") not in ROLES:
            raise UserError("Selecciona un rol válido.")
        if data["role"] in {"gestor", "consulta"} and not data["department_id"]:
            raise UserError("Los perfiles Gestor y Consulta necesitan un área.")
    else:
        data["code"] = clean_text(data.get("code"), "Código", 2, 20).upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,19}", data["code"]):
            raise UserError("Código: usa letras sin tildes, números, guion o guion bajo.")
        data["name"] = clean_text(data.get("name"), "Nombre", 3, 120)
    if entity == "departments":
        if data.get("unit_type") not in UNIT_TYPES:
            raise UserError("Selecciona un tipo de área.")
        source = clean_text(data.get("source_url"), "Enlace de referencia", 0, 1000)
        if source and not re.fullmatch(r"https://[^\s/?#]+(?:[/?#][^\s]*)?", source):
            raise UserError("El enlace de referencia debe ser una dirección HTTPS válida.")
        data["source_url"] = source or None
    elif entity == "procedures":
        data["requirements"] = clean_text(data.get("requirements"), "Requisitos", 0, 5000)
        data["legal_basis"] = clean_text(data.get("legal_basis"), "Sustento", 0, 2000) or None
        if type(data.get("is_official")) is not bool:
            raise UserError("Indica si la ficha tiene sustento oficial.")
        if data["is_official"] and not data["legal_basis"]:
            raise UserError("Añade el sustento y la referencia antes de marcar la ficha oficial.")
        for field in ("fee_pen", "deadline_days"):
            value = str(data.get(field) or "").strip()
            # El cero es un importe válido, pero no un plazo válido.
            if data.get(field) == 0:
                value = "0"
            data[field] = None
            if not value:
                continue
            try:
                number = Decimal(value)
                if not number.is_finite():
                    raise ValueError
                if field == "fee_pen":
                    if (
                        not 0 <= number <= Decimal("9999999999.99")
                        or number.as_tuple().exponent < -2
                    ):
                        raise ValueError
                    data[field] = str(number)
                else:
                    if not 1 <= number <= 3650 or number != int(number):
                        raise ValueError
                    data[field] = int(number)
            except (InvalidOperation, ValueError, OverflowError):
                label = (
                    "Importe: máximo dos decimales, desde 0"
                    if field == "fee_pen"
                    else "Plazo: entero entre 1 y 3650"
                )
                raise UserError(f"{label}. Deja vacío si no está definido.") from None
    common = {key, "is_active"}
    fields = {
        "departments": {"code", "name", "unit_type", "source_url"},
        "procedures": {
            "code",
            "name",
            "requirements",
            "department_id",
            "is_official",
            "legal_basis",
            "fee_pen",
            "deadline_days",
        },
        "staff_profiles": {"display_name", "role", "department_id"},
    }
    return {field: data[field] for field in common | fields[entity]}
