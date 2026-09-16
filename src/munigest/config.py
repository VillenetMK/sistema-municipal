"""Configuración explícita: nunca sustituir una conexión fallida con datos de prueba."""

import base64
import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

from dotenv import load_dotenv

try:
    from munigest._build_settings import CONFIG as BUILD_CONFIG
except ModuleNotFoundError:
    BUILD_CONFIG = {}


@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    name: str = "MuniGest"
    project_ref: str = "lxvmwjcqdjoidgpinmgm"
    url: str = ""
    key: str = field(default="", repr=False)

    @classmethod
    def from_env(cls):
        load_dotenv(override=False)

        def setting(name, default=""):
            return os.getenv(name, BUILD_CONFIG.get(name, default))

        result = cls(
            mode=setting("MUNIGEST_MODE", "demo"),
            name=setting("MUNIGEST_NAME", "MuniGest"),
            project_ref=setting("SUPABASE_PROJECT_REF", "lxvmwjcqdjoidgpinmgm"),
            url=setting("SUPABASE_URL").rstrip("/"),
            key=setting("SUPABASE_PUBLISHABLE_KEY"),
        )
        result.validate()
        return result

    def validate(self):
        if self.mode not in {"demo", "supabase"}:
            raise ValueError("MUNIGEST_MODE debe ser demo o supabase.")
        if self.mode == "demo":
            return
        parsed = urlparse(self.url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != f"{self.project_ref}.supabase.co"
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("La URL no coincide con el proyecto Supabase configurado.")
        if self.project_ref == "kslzmrddrhfyyrxyfmbw":
            raise ValueError("EcoSphere es otro proyecto. Usa la base municipal.")
        if self.key.startswith("sb_publishable_"):
            return
        # Compatibilidad con anon heredada. Esto NO autentica usuarios ni valida JWT.
        try:
            segment = self.key.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))
            if claims.get("role") == "anon" and claims.get("ref") == self.project_ref:
                return
        except (IndexError, ValueError, TypeError):
            pass
        raise ValueError(
            "Configura una clave publicable del proyecto municipal; no una clave secreta."
        )
