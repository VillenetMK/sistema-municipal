"""Conserva únicamente los tokens de la sesión web en la pestaña actual."""

import json
import math
import sys

from munigest.domain import UserError


class WebSessionStore:
    def __init__(self, storage, project_ref):
        self.storage = storage
        self.key = f"munigest.{project_ref}.session.v1"

    async def load(self):
        try:
            raw = await self.storage.get(self.key)
        except Exception:
            raise UserError("El navegador no pudo recuperar la sesión guardada.") from None
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            tokens = {name: data[name] for name in ("access_token", "refresh_token")}
            expiry = data["expires_at"]
            if not all(
                isinstance(token, str) and 0 < len(token) <= 16384 for token in tokens.values()
            ):
                raise ValueError
            if type(expiry) not in (int, float) or not math.isfinite(expiry):
                raise ValueError
            return {**tokens, "expires_at": expiry}
        except (ValueError, TypeError, KeyError):
            await self.clear()
            return None

    async def save(self, session):
        # Nunca guardar contraseña, perfil, permisos ni documentos.
        data = {name: session[name] for name in ("access_token", "refresh_token", "expires_at")}
        try:
            await self.storage.set(self.key, json.dumps(data))
        except Exception:
            raise UserError(
                "El navegador bloqueó el almacenamiento de la sesión. Revisa sus permisos e inténtalo nuevamente."
            ) from None

    async def clear(self):
        try:
            await self.storage.remove(self.key)
        except Exception:
            raise UserError(
                "No se pudo borrar la sesión guardada. Cierra esta pestaña para finalizar el acceso."
            ) from None


def browser_session_store(page, project_ref):
    if sys.platform != "emscripten":
        return None
    from flet_secure_storage import SecureStorage, WebOptions

    storage = SecureStorage(
        web_options=WebOptions(
            db_name=f"munigest_{project_ref}",
            public_key=f"munigest_{project_ref}_key",
            use_session_storage=True,
        )
    )
    page.services.append(storage)
    return WebSessionStore(storage, project_ref)
