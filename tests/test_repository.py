import asyncio
import json
import time

import httpx
import pytest

from munigest.config import Settings
from munigest.domain import SessionExpired, UserError
from munigest.repository import SupabaseRepository

CONFIG = Settings(
    mode="supabase", url="https://lxvmwjcqdjoidgpinmgm.supabase.co", key="sb_publishable_test"
)


def test_login_requires_active_authorized_profile():
    def handler(request):
        if request.url.path == "/auth/v1/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "test-access",
                    "refresh_token": "test-refresh",
                    "expires_in": 3600,
                    "user": {"id": "u1"},
                },
            )
        return httpx.Response(200, json=[])

    async def exercise():
        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler))
        with pytest.raises(UserError, match="perfil municipal activo"):
            await repo.sign_in("demo@example.invalid", "test-only")
        assert repo.session is None
        await repo.close()

    asyncio.run(exercise())


def test_expired_session_refreshes_once_for_concurrent_reads():
    refreshes = []

    async def handler(request):
        if request.url.path == "/auth/v1/token":
            refreshes.append(1)
            await asyncio.sleep(0)
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            )
        assert request.headers["Authorization"] == "Bearer new-access"
        return httpx.Response(200, json=[])

    async def exercise():
        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler))
        repo.session = {"access_token": "old", "refresh_token": "r", "expires_at": time.time() - 1}
        await asyncio.gather(repo.departments(), repo.procedures())
        assert len(refreshes) == 1
        await repo.close()

    asyncio.run(exercise())


def test_api_permissions_error_does_not_expose_response_contents():
    def handler(_):
        return httpx.Response(403, json={"message": "sensitive database detail"})

    async def exercise():
        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler))
        repo.session = {
            "access_token": "test",
            "refresh_token": "r",
            "expires_at": time.time() + 3600,
        }
        with pytest.raises(UserError) as exc:
            await repo.departments()
        assert "sensitive" not in str(exc.value)
        await repo.close()

    asyncio.run(exercise())


def test_failed_refresh_discards_session():
    async def exercise():
        repo = SupabaseRepository(
            CONFIG, httpx.MockTransport(lambda _: httpx.Response(400, json={}))
        )
        repo.session = {"access_token": "test", "refresh_token": "r", "expires_at": 0}
        with pytest.raises(SessionExpired):
            await repo.departments()
        assert repo.session is None
        await repo.close()

    asyncio.run(exercise())


def test_mutation_is_not_automatically_retried_after_timeout():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("network failure", request=request)

    async def exercise():
        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler))
        repo.session = {
            "access_token": "test",
            "refresh_token": "r",
            "expires_at": time.time() + 3600,
        }
        with pytest.raises(UserError):
            await repo.advance_case(
                {"id": "case", "version": 1}, "en_revision", "dept", "Motivo de prueba"
            )
        assert len(calls) == 1
        body = json.loads(calls[0].content)
        assert body["expected_version"] == 1
        await repo.close()

    asyncio.run(exercise())
