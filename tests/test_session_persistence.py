import asyncio
import json
import time

import httpx
import pytest

from munigest.config import Settings
from munigest.domain import SessionExpired, UserError
from munigest.repository import SupabaseRepository
from munigest.session_storage import WebSessionStore

CONFIG = Settings(
    mode="supabase", url="https://lxvmwjcqdjoidgpinmgm.supabase.co", key="sb_publishable_test"
)


class Storage:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value):
        self.values[key] = value

    async def remove(self, key):
        self.values.pop(key, None)


def session(**extra):
    return {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": time.time() + 3600,
        **extra,
    }


def test_reload_validates_user_and_current_role_then_logout_removes_saved_session():
    async def exercise():
        storage = Storage()
        store = WebSessionStore(storage, CONFIG.project_ref)
        role, paths = ["admin"], []

        def handler(request):
            paths.append(request.url.path)
            if request.url.path == "/auth/v1/token":
                return httpx.Response(200, json={**session(), "user": {"id": "user"}})
            if request.url.path == "/auth/v1/user":
                return httpx.Response(200, json={"id": "user"})
            if request.url.path == "/auth/v1/logout":
                assert store.key not in storage.values
                assert request.url.params["scope"] == "local"
                return httpx.Response(204)
            assert request.url.params["user_id"] == "eq.user"
            return httpx.Response(
                200, json=[{"user_id": "user", "role": role[0], "is_active": True}]
            )

        transport = httpx.MockTransport(handler)
        first = SupabaseRepository(CONFIG, transport, session_store=store)
        await first.sign_in("admin", "password-not-saved")
        await first.close()  # Recargar cierra el cliente, pero no la sesión guardada.
        assert "password-not-saved" not in storage.values[store.key]
        assert "role" not in storage.values[store.key]
        role[0] = "consulta"
        second = SupabaseRepository(CONFIG, transport, session_store=store)
        assert (await second.restore_session())["role"] == "consulta"
        assert paths[-2:] == ["/auth/v1/user", "/rest/v1/staff_profiles"]
        await second.sign_out()
        await second.close()
        third = SupabaseRepository(CONFIG, transport, session_store=store)
        assert await third.restore_session() is None
        await third.close()

    asyncio.run(exercise())


def test_expired_saved_session_rotates_tokens_once_and_persists_them():
    async def exercise():
        store = WebSessionStore(Storage(), CONFIG.project_ref)
        await store.save(session(expires_at=0))
        calls = []

        async def handler(request):
            calls.append(request.url.path)
            if request.url.path == "/auth/v1/token":
                assert request.url.params["grant_type"] == "refresh_token"
                assert json.loads(request.content) == {"refresh_token": "refresh"}
                await asyncio.sleep(0)
                return httpx.Response(
                    200, json=session(access_token="new", refresh_token="rotated")
                )
            assert request.headers["Authorization"] == "Bearer new"
            if request.url.path == "/auth/v1/user":
                return httpx.Response(200, json={"id": "user"})
            return httpx.Response(200, json=[{"user_id": "user", "role": "consulta"}])

        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler), session_store=store)
        await repo.restore_session()
        assert calls.count("/auth/v1/token") == 1
        assert (await store.load())["refresh_token"] == "rotated"
        await repo.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("failure", ["revoked", "inactive"])
def test_revoked_session_or_inactive_profile_cannot_be_restored(failure):
    async def exercise():
        store = WebSessionStore(Storage(), CONFIG.project_ref)
        await store.save(session())

        def handler(request):
            if request.url.path == "/auth/v1/user":
                return httpx.Response(401 if failure == "revoked" else 200, json={"id": "user"})
            return httpx.Response(200, json=[])

        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler), session_store=store)
        with pytest.raises(UserError):
            await repo.restore_session()
        assert repo.session is None and repo.profile is None
        assert await store.load() is None
        await repo.close()

    asyncio.run(exercise())


@pytest.mark.parametrize("status", [400, 401, 429, 503, "offline"])
def test_only_invalid_refresh_discards_tokens_transient_failures_allow_retry(status):
    async def exercise():
        store = WebSessionStore(Storage(), CONFIG.project_ref)
        await store.save(session(expires_at=0))

        def handler(request):
            if status == "offline":
                raise httpx.ConnectError("offline", request=request)
            return httpx.Response(status, json={})

        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler), session_store=store)
        with pytest.raises(UserError):
            await repo.restore_session()
        saved = await store.load()
        assert (saved is None) == (status in {400, 401})
        await repo.close()

    asyncio.run(exercise())


def test_logout_offline_still_removes_tokens():
    async def exercise():
        store = WebSessionStore(Storage(), CONFIG.project_ref)
        await store.save(session())

        def handler(request):
            raise httpx.ConnectError("offline", request=request)

        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler), session_store=store)
        repo.session = await store.load()
        with pytest.raises(UserError):
            await repo.sign_out()
        assert await store.load() is None
        assert repo.session is None
        await repo.close()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "raw",
    ["broken", "null", "[]", "{}", '{"access_token":123}', json.dumps(session(expires_at="never"))],
)
def test_corrupt_storage_is_cleared_only_for_this_project(raw):
    async def exercise():
        storage = Storage()
        store = WebSessionStore(storage, CONFIG.project_ref)
        storage.values = {store.key: raw, "other-app": "keep"}
        assert await store.load() is None
        assert storage.values == {"other-app": "keep"}

    asyncio.run(exercise())


def test_logout_during_refresh_cannot_restore_session():
    async def exercise():
        store = WebSessionStore(Storage(), CONFIG.project_ref)
        repo = None

        async def handler(request):
            await repo._discard_session()
            return httpx.Response(200, json=session(access_token="new", refresh_token="rotated"))

        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler), session_store=store)
        await repo._save_session(session(expires_at=0))
        with pytest.raises(SessionExpired):
            await repo.departments()
        assert repo.session is None
        assert await store.load() is None
        await repo.close()

    asyncio.run(exercise())
