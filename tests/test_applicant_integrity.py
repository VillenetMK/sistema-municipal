import asyncio
import copy
import json
import time
from uuid import uuid4

import httpx
import pytest

from munigest.demo import DemoRepository
from munigest.domain import UserError
from munigest.repository import SupabaseRepository
from tests.test_repository import CONFIG


def test_contact_per_case_and_admin_correction_preserve_history():
    async def exercise():
        repo = DemoRepository()
        await repo.sign_in()
        first = (await repo.list_cases())[0]
        person = next(
            p for p in await repo.admin_records("applicants") if p["id"] == first["applicant_id"]
        )
        corrected = await repo.admin_save(
            "applicants",
            {**person, "email": "nuevo@example.test"},
            person["version"],
            "Actualización ficticia de datos de contacto.",
        )
        assert corrected["version"] == 2
        assert (await repo.get_case(first["id"]))["applicant_snapshot"] == first[
            "applicant_snapshot"
        ]
        draft = {**first, "request_id": str(uuid4()), "email": "solicitud@example.test"}
        second = await repo.create_case(draft)
        assert second["applicant"]["email"] == "solicitud@example.test"
        assert len(await repo.admin_history("applicants", person["id"])) == 1
        with pytest.raises(UserError, match="Otro usuario"):
            await repo.admin_save(
                "applicants", person, 1, "Intento de corrección con versión antigua."
            )

    asyncio.run(exercise())


@pytest.mark.parametrize("lost_response", [False, True])
def test_upload_finalizes_once_and_recovers_a_lost_confirmation(lost_response):
    saved = []
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path.startswith("/storage/"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/finalize_document"):
            metadata = json.loads(request.content)["metadata"]
            assert "created_by" not in metadata
            saved.append({**metadata, "verified_at": "2026-09-29T00:00:00Z"})
            if lost_response:
                raise httpx.ReadTimeout("test-only", request=request)
            return httpx.Response(200, json=saved[0])
        assert request.url.params["id"] == "eq." + saved[0]["id"]
        return httpx.Response(200, json=saved)

    async def exercise():
        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler))
        repo.profile = {"user_id": str(uuid4()), "role": "admin"}
        repo.session = {
            "access_token": "test",
            "refresh_token": "test",
            "expires_at": time.time() + 3600,
        }
        try:
            result = await repo.upload_document(str(uuid4()), "solicitud.pdf", b"%PDF-1.7\nprueba")
            assert result["verified_at"]
            assert len(saved) == 1
            assert sum(method == "POST" for method, _ in calls) == 2
        finally:
            await repo.close()

    asyncio.run(exercise())


def test_case_details_use_reception_snapshot_instead_of_edited_identity():
    case = {
        "id": "case",
        "applicant": {"full_name": "Nombre corregido"},
        "applicant_snapshot": {"full_name": "Nombre al recibir", "email": "original@example.test"},
    }

    async def exercise():
        repo = SupabaseRepository(
            CONFIG, httpx.MockTransport(lambda _: httpx.Response(200, json=[copy.deepcopy(case)]))
        )
        repo.session = {
            "access_token": "test",
            "refresh_token": "test",
            "expires_at": time.time() + 3600,
        }
        try:
            result = await repo.get_case("case")
            assert result["applicant"] == case["applicant_snapshot"]
        finally:
            await repo.close()

    asyncio.run(exercise())
