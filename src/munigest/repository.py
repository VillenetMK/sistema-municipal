"""Cliente asíncrono de Supabase. Una instancia y una sesión por usuario de Flet."""

import asyncio
import hashlib
import re
import time
from pathlib import PurePath
from uuid import uuid4

import httpx

from munigest.domain import SessionExpired, UserError, validate_attachment, validate_draft


class SupabaseRepository:
    def __init__(self, settings, transport=None):
        settings.validate()
        self.login_aliases = (
            {"admin": "admin.piloto@munigest.invalid"}
            if settings.project_ref == "lxvmwjcqdjoidgpinmgm"
            else {}
        )
        self.client = httpx.AsyncClient(
            base_url=settings.url,
            headers={"apikey": settings.key},
            timeout=httpx.Timeout(25, connect=8),
            transport=transport,
            follow_redirects=False,
        )
        self.session = None
        self.profile = None
        self._refresh_lock = asyncio.Lock()

    async def _request(self, method, path, *, authenticated=True, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        if authenticated:
            await self._ensure_session()
            headers["Authorization"] = f"Bearer {self.session['access_token']}"
        try:
            response = await self.client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError:
            raise UserError(
                "No se pudo contactar con el servidor. Revisa tu conexión y vuelve a intentarlo."
            ) from None
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {}
            if response.status_code == 401 and authenticated:
                self.session = None
                raise SessionExpired("Tu sesión ha vencido. Inicia sesión nuevamente.")
            if not authenticated and response.status_code in {400, 401, 422}:
                raise UserError(
                    "No se pudo iniciar sesión. Revisa tus credenciales y la confirmación del correo."
                )
            if body.get("code") == "P0001":
                raise UserError(str(body.get("message", "Operación no permitida."))[:250])
            if response.status_code == 403:
                raise UserError("Tu cuenta no tiene permiso para realizar esta operación.")
            if response.status_code == 409:
                raise UserError(
                    "El registro cambió o ya existe. Actualiza la bandeja antes de continuar."
                )
            if response.status_code == 429:
                raise UserError(
                    "Hay demasiados intentos. Espera un momento antes de volver a intentarlo."
                )
            raise UserError(
                "No se pudo completar la operación. Verifica la configuración del proyecto."
            )
        return response

    def _save_session(self, data):
        self.session = {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_at": data.get("expires_at", time.time() + data.get("expires_in", 3600)),
        }

    async def _ensure_session(self):
        if not self.session:
            raise SessionExpired("Inicia sesión para continuar.")
        if self.session["expires_at"] > time.time() + 60:
            return
        async with self._refresh_lock:
            if not self.session:
                raise SessionExpired("Inicia sesión para continuar.")
            if self.session["expires_at"] > time.time() + 60:
                return
            try:
                response = await self._request(
                    "POST",
                    "/auth/v1/token",
                    authenticated=False,
                    params={"grant_type": "refresh_token"},
                    json={"refresh_token": self.session["refresh_token"]},
                )
                self._save_session(response.json())
            except UserError:
                self.session = None
                raise SessionExpired(
                    "No se pudo renovar tu sesión. Inicia sesión nuevamente."
                ) from None

    async def sign_in(self, email, password):
        email = email.strip()
        email = self.login_aliases.get(email.casefold(), email)
        response = await self._request(
            "POST",
            "/auth/v1/token",
            authenticated=False,
            params={"grant_type": "password"},
            json={"email": email, "password": password},
        )
        data = response.json()
        self._save_session(data)
        try:
            response = await self._request(
                "GET",
                "/rest/v1/staff_profiles",
                params={
                    "user_id": f"eq.{data['user']['id']}",
                    "select": "*",
                    "is_active": "eq.true",
                },
            )
            profiles = response.json()
            if not profiles:
                raise UserError(
                    "Tu cuenta todavía no tiene un perfil municipal activo. Contacta al administrador."
                )
            self.profile = profiles[0]
            return self.profile
        except Exception:
            self.session = None
            self.profile = None
            raise

    async def sign_out(self):
        try:
            if self.session:
                await self._request("POST", "/auth/v1/logout", params={"scope": "local"})
        finally:
            self.session = None
            self.profile = None

    async def close(self):
        self.session = None
        self.profile = None
        await self.client.aclose()

    async def departments(self):
        return (
            await self._request(
                "GET",
                "/rest/v1/departments",
                params={"select": "*", "is_active": "eq.true", "order": "name"},
            )
        ).json()

    async def procedures(self):
        return (
            await self._request(
                "GET",
                "/rest/v1/procedures",
                params={"select": "*", "is_active": "eq.true", "order": "name"},
            )
        ).json()

    async def settings(self):
        rows = (
            await self._request(
                "GET", "/rest/v1/municipal_settings", params={"select": "*", "id": "eq.1"}
            )
        ).json()
        return rows[0] if rows else {"institution_name": "Municipalidad por configurar"}

    async def metrics(self):
        return (await self._request("POST", "/rest/v1/rpc/case_metrics", json={})).json()

    async def list_cases(self, query="", status="", offset=0, limit=51):
        params = {
            "select": "*,applicant:applicants(full_name,document_type,document_number),department:departments(name)",
            "order": "created_at.desc,id.desc",
            "offset": str(offset),
            "limit": str(limit),
        }
        if status:
            params["status"] = f"eq.{status}"
        term = re.sub(r"[^0-9A-Za-zÀ-ÿ -]", " ", query).strip()[:60]
        if term:
            params["or"] = f"(reference.ilike.*{term}*,title.ilike.*{term}*)"
        return (await self._request("GET", "/rest/v1/cases", params=params)).json()

    async def get_case(self, case_id):
        rows = (
            await self._request(
                "GET",
                "/rest/v1/cases",
                params={
                    "id": f"eq.{case_id}",
                    "select": "*,applicant:applicants(*),department:departments(name)",
                },
            )
        ).json()
        if not rows:
            raise UserError("El expediente ya no está disponible en tu área. Actualiza la bandeja.")
        return rows[0]

    async def events(self, case_id):
        return (
            await self._request(
                "GET",
                "/rest/v1/case_events",
                params={
                    "case_id": f"eq.{case_id}",
                    "select": "*",
                    "order": "created_at.desc,id.desc",
                },
            )
        ).json()

    async def create_case(self, draft):
        return (
            await self._request(
                "POST", "/rest/v1/rpc/register_case", json={"payload": validate_draft(draft)}
            )
        ).json()

    async def advance_case(self, case, target, department_id, note):
        return (
            await self._request(
                "POST",
                "/rest/v1/rpc/advance_case",
                json={
                    "case_id": case["id"],
                    "expected_version": case["version"],
                    "new_status": target,
                    "new_department": department_id,
                    "note": note.strip(),
                },
            )
        ).json()

    async def documents(self, case_id):
        return (
            await self._request(
                "GET",
                "/rest/v1/case_documents",
                params={"case_id": f"eq.{case_id}", "select": "*", "order": "created_at.desc"},
            )
        ).json()

    async def upload_document(self, case_id, filename, content):
        filename, mime = validate_attachment(filename, content)
        document_id = str(uuid4())
        path = f"{case_id}/{document_id}{PurePath(filename).suffix.lower()}"
        await self._request(
            "POST",
            f"/storage/v1/object/expedientes/{path}",
            content=content,
            headers={"Content-Type": mime, "x-upsert": "false"},
        )
        try:
            response = await self._request(
                "POST",
                "/rest/v1/case_documents",
                headers={"Prefer": "return=representation"},
                json={
                    "id": document_id,
                    "case_id": case_id,
                    "file_name": filename,
                    "object_path": path,
                    "media_type": mime,
                    "size_bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "created_by": self.profile["user_id"],
                },
            )
        except UserError as exc:
            # No se borra un objeto documental automáticamente. Reconciliación por administrador.
            raise UserError(
                "El archivo se subió, pero no se pudo registrar el adjunto. Informa al administrador antes de repetir la carga."
            ) from exc
        return response.json()[0]

    async def download_document(self, document):
        response = await self._request(
            "GET", f"/storage/v1/object/authenticated/expedientes/{document['object_path']}"
        )
        data = response.content
        if hashlib.sha256(data).hexdigest() != document["sha256"]:
            raise UserError("El contenido del archivo no coincide con su huella registrada.")
        return data
