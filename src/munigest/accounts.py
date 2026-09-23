"""Alta por invitación y recuperación mediante Supabase Auth, sin claves administrativas."""

import re
from urllib.parse import parse_qs, urlparse

import httpx

from munigest.domain import ROLES, UserError, clean_text


def account_email(value):
    value = (value or "").strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise UserError("Escribe un correo real al que puedas acceder.")
    if value.endswith((".invalid", ".test", ".example")):
        raise UserError("Las cuentas piloto no reciben correo. Usa una cuenta con correo real.")
    return value


def new_password(value, confirmation):
    if len(value) < 12 or len(value.encode("utf-8")) > 72:
        raise UserError(
            "La nueva contraseña necesita al menos 12 caracteres y un máximo de 72 bytes."
        )
    if value != confirmation:
        raise UserError("Las contraseñas no coinciden.")
    return value


def invitation_payload(email, name, role, department, reason):
    if role not in ROLES or not department:
        raise UserError("Selecciona un rol y un área activa.")
    return {
        "email": account_email(email),
        "display_name": clean_text(name, "Nombre", 3, 120),
        "role": role,
        "department_id": department,
        "reason": clean_text(reason, "Motivo", 10, 500),
    }


def verification_payload(value, email, kind, project_url):
    """Nunca navegar enlaces recibidos ni aceptar un token de otro proyecto o propósito."""
    value = (value or "").strip()
    if kind not in {"signup", "recovery"}:
        raise UserError("Tipo de verificación inválido.")
    if re.fullmatch(r"[0-9]{6,10}", value):
        return {"email": account_email(email), "token": value, "type": kind}
    parsed, expected = urlparse(value), urlparse(project_url)
    params = parse_qs(parsed.query)
    if (
        parsed.scheme != "https"
        or parsed.netloc != expected.netloc
        or parsed.path != "/auth/v1/verify"
        or parsed.fragment
        or params.get("type") != [kind]
        or len(params.get("token", [])) != 1
        or not re.fullmatch(r"[A-Za-z0-9_-]{20,512}", params["token"][0])
    ):
        raise UserError(
            "Copia el enlace original del correo de esta operación, o su código numérico."
        )
    return {"token_hash": params["token"][0], "type": kind}


class AccountOperations:
    async def account_request(self, path, *, method="POST", access_token=None, **kwargs):
        headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
        try:
            response = await self.client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError:
            raise UserError(
                "No se pudo confirmar la operación. Revisa tu conexión antes de repetirla."
            ) from None
        if not 200 <= response.status_code < 300:
            if response.status_code == 429:
                raise UserError("Espera unos minutos antes de solicitar otro correo o código.")
            if response.status_code >= 500:
                raise UserError(
                    "No se completó la operación. El administrador debe revisar Auth y el envío de correo."
                )
            raise UserError(
                "No se completó la operación. Revisa los datos; el código puede haber vencido o estar usado."
            )
        return response.json() if response.content else {}

    async def invitations(self, offset=0):
        return (
            await self._request(
                "POST",
                "/rest/v1/rpc/admin_invitations",
                json={
                    "operation": "list",
                    "payload": {"offset": offset},
                },
            )
        ).json()

    async def create_invitation(self, invitation_id, token, **fields):
        payload = invitation_payload(**fields)
        return (
            await self._request(
                "POST",
                "/rest/v1/rpc/admin_invitations",
                json={
                    "operation": "create",
                    "payload": {**payload, "id": invitation_id, "token": token},
                },
            )
        ).json()

    async def revoke_invitation(self, invitation_id, reason):
        return (
            await self._request(
                "POST",
                "/rest/v1/rpc/admin_invitations",
                json={
                    "operation": "revoke",
                    "payload": {
                        "id": invitation_id,
                        "reason": clean_text(reason, "Motivo", 10, 500),
                    },
                },
            )
        ).json()

    async def activate_account(self, email, token, password, confirmation):
        token = (token or "").strip()
        if not re.fullmatch(r"[a-f0-9]{64}", token):
            raise UserError("Copia completo el código de invitación que te dio el administrador.")
        result = await self.account_request(
            "/auth/v1/signup",
            json={
                "email": account_email(email),
                "password": new_password(password, confirmation),
                "data": {"municipal_invitation": token},
            },
        )
        # Si Auth no exige confirmar correo, cerrar esa sesión: el acceso pasa por el login normal.
        if result.get("access_token"):
            await self.account_request(
                "/auth/v1/logout", access_token=result["access_token"], params={"scope": "local"}
            )
            return True
        return False

    async def resend_confirmation(self, email):
        await self.account_request(
            "/auth/v1/resend", json={"type": "signup", "email": account_email(email)}
        )

    async def request_recovery(self, email):
        await self.account_request("/auth/v1/recover", json={"email": account_email(email)})

    async def verify_account(self, email, value, kind, password=None, confirmation=None):
        if kind == "recovery":
            new_password(password or "", confirmation or "")
        payload = verification_payload(value, email, kind, str(self.client.base_url))
        result = await self.account_request("/auth/v1/verify", json=payload)
        access = result.get("access_token")
        if not access:
            raise UserError("No se obtuvo una sesión de verificación. Solicita un correo nuevo.")
        try:
            if kind == "recovery":
                await self.account_request(
                    "/auth/v1/user", method="PUT", access_token=access, json={"password": password}
                )
        finally:
            try:
                await self.account_request(
                    "/auth/v1/logout", access_token=access, params={"scope": "local"}
                )
            except UserError:
                pass
        # No sustituir la sesión de trabajo por la sesión transitoria de recuperación.
