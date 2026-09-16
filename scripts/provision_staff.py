"""Alta individual por un operador de confianza. Sin --apply solo muestra el plan.

La clave administrativa se lee del entorno o de un prompt oculto. Nunca se carga
en Flet, se escribe en archivos ni se incluye en los paquetes nativos.
"""

import argparse
import getpass
import os
import re
import sys
from pathlib import Path
from uuid import UUID

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from munigest.domain import ROLES, UserError, clean_text  # noqa: E402
from munigest.institution import INSTITUTION_NAME  # noqa: E402

PROJECT_URL = "https://lxvmwjcqdjoidgpinmgm.supabase.co"


def validate_person(email, name, role, department):
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise UserError("Ingresa el correo real de la persona.")
    if role not in ROLES:
        raise UserError("El rol no existe.")
    if not re.fullmatch(r"[A-Z0-9_]{2,20}", department):
        raise UserError("Indica el código del área, por ejemplo MP o GTIE.")
    return email, clean_text(name, "Nombre", 3, 120), role, department


def validate_password(password):
    if len(password) < 12 or len(password.encode("utf-8")) > 72:
        raise UserError("Usa al menos 12 caracteres y como máximo 72 bytes UTF-8.")


class StaffProvisioner:
    """Cliente administrativo exclusivo del proyecto municipal."""

    def __init__(self, key, *, url=PROJECT_URL, transport=None):
        if url.rstrip("/") != PROJECT_URL:
            raise UserError("La herramienta solo admite el proyecto municipal de Chiclayo.")
        if not re.fullmatch(r"sb_secret_[A-Za-z0-9_-]{16,}", key):
            raise UserError(
                "Se necesita una clave administrativa sb_secret del proyecto municipal."
            )
        self.client = httpx.Client(
            base_url=PROJECT_URL,
            headers={"apikey": key},
            timeout=httpx.Timeout(25, connect=8),
            follow_redirects=False,
            transport=transport,
        )

    def close(self):
        self.client.close()

    def request(self, method, path, **kwargs):
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.HTTPError:
            raise UserError(
                "No se pudo confirmar la operación. Revisa Auth antes de repetir un alta; "
                "una escritura puede haber llegado al servidor."
            ) from None
        if not 200 <= response.status_code < 300:
            raise UserError(
                f"Supabase rechazó la operación (HTTP {response.status_code}). "
                "Revisa permisos y si la cuenta ya existe. No se reintentó automáticamente."
            )
        return response.json()

    def provision(
        self, *, email, name, role, department, user_id=None, password=None, email_verified=False
    ):
        email, name, role, department = validate_person(email, name, role, department)
        if email.rsplit("@", 1)[1] in {"example.com", "example.org", "example.net", "ejemplo.com"}:
            raise UserError("Sustituye el correo de ejemplo por el de una persona real.")
        if not user_id:
            if not email_verified:
                raise UserError("Verifica la titularidad del correo antes de crear la cuenta.")
            validate_password(password or "")
        else:
            try:
                user_id = str(UUID(user_id))
            except (ValueError, TypeError):
                raise UserError("El ID del usuario Auth no es válido.") from None

        settings = self.request(
            "GET",
            "/rest/v1/municipal_settings",
            params={"id": "eq.1", "select": "institution_name"},
        )
        if not settings or settings[0]["institution_name"] != INSTITUTION_NAME:
            raise UserError("La identidad institucional no coincide con Chiclayo.")
        departments = self.request(
            "GET",
            "/rest/v1/departments",
            params={
                "code": f"eq.{department}",
                "is_active": "eq.true",
                "select": "id,name",
            },
        )
        if len(departments) != 1:
            raise UserError("El área no existe o está desactivada. No se creó ninguna cuenta.")

        if user_id:
            user = self.request("GET", f"/auth/v1/admin/users/{user_id}")
        else:
            user = self.request(
                "POST",
                "/auth/v1/admin/users",
                json={
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"display_name": name},
                },
            )
        user_id = str(UUID(user["id"]))
        if user.get("email", "").lower() != email or not user.get("email_confirmed_at"):
            raise UserError("La cuenta Auth no coincide o su correo aún no está confirmado.")

        profile = {
            "user_id": user_id,
            "display_name": name,
            "role": role,
            "department_id": departments[0]["id"],
            "is_active": True,
        }
        query = {"user_id": f"eq.{user_id}", "select": ",".join(profile)}
        try:
            existing = self.request("GET", "/rest/v1/staff_profiles", params=query)
            if existing:
                if all(existing[0].get(key) == value for key, value in profile.items()):
                    return user_id, False
                raise UserError(
                    "Ya existe un perfil diferente; el alta no modifica permisos existentes."
                )
            # Un alta concurrente nunca sobrescribe un perfil ni eleva sus privilegios.
            self.request(
                "POST",
                "/rest/v1/staff_profiles",
                params={"on_conflict": "user_id"},
                headers={"Prefer": "resolution=ignore-duplicates,return=representation"},
                json=profile,
            )
            saved = self.request("GET", "/rest/v1/staff_profiles", params=query)
            if not saved or any(saved[0].get(k) != v for k, v in profile.items()):
                raise UserError("El perfil guardado no coincide con el solicitado.")
        except UserError as exc:
            raise UserError(
                f"Auth ID: {user_id}. {exc} "
                "La cuenta Auth se conservó. Revisa su perfil; para reanudar usa --user-id."
            ) from None
        return user_id, True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Alta de personal de MuniGest Chiclayo")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=ROLES, required=True)
    parser.add_argument("--department", required=True)
    parser.add_argument("--user-id", help="Cuenta existente y confirmada; no cambia su contraseña")
    parser.add_argument(
        "--verified-email",
        action="store_true",
        help="El operador ya verificó la titularidad del correo de la nueva cuenta",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Ejecutar el alta; sin esto solo muestra el plan"
    )
    args = parser.parse_args(argv)
    try:
        email, name, role, department = validate_person(
            args.email, args.name, args.role, args.department
        )
        print(f"MPCH: {name} <{email}> · {ROLES[role]} · {department}")
        if not args.apply:
            print("Plan preparado. No se conectó a Supabase ni se creó ninguna cuenta.")
            return 0
        if not args.user_id and not args.verified_email:
            raise UserError("Para un correo ya verificado por el operador, añade --verified-email.")
        if not sys.stdin.isatty():
            raise UserError("Ejecuta el alta en una terminal interactiva del operador autorizado.")
        key = os.getenv("SUPABASE_SECRET_KEY") or getpass.getpass("Clave administrativa (oculta): ")
        password = None
        if not args.user_id:
            password = getpass.getpass("Contraseña individual (oculta): ")
            validate_password(password)
            if password != getpass.getpass("Repite la contraseña: "):
                raise UserError("Las contraseñas no coinciden.")
        provisioner = StaffProvisioner(key, url=os.getenv("SUPABASE_URL", PROJECT_URL))
        try:
            user_id, created = provisioner.provision(
                email=email,
                name=name,
                role=role,
                department=department,
                user_id=args.user_id,
                password=password,
                email_verified=args.verified_email,
            )
        finally:
            provisioner.close()
        print(f"{'Perfil creado y comprobado' if created else 'Perfil ya existente'}: {user_id}")
        return 0
    except UserError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (KeyError, ValueError, TypeError):
        print(
            "Respuesta inesperada. Comprueba Auth y el perfil antes de repetir el alta.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
