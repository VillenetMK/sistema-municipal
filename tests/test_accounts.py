import asyncio
import json
from dataclasses import replace

import httpx
import pytest
from test_ui import PageStub, assert_valid_wrapping_layout

from munigest.account_ui import AccountScreen
from munigest.accounts import account_email, new_password, verification_payload
from munigest.config import Settings
from munigest.demo import DemoRepository
from munigest.domain import UserError
from munigest.repository import SupabaseRepository
from munigest.ui import MunicipalApp

CONFIG = Settings(
    mode="supabase", url="https://lxvmwjcqdjoidgpinmgm.supabase.co", key="sb_publishable_test"
)


@pytest.mark.parametrize(
    "email", ["admin", "admin.piloto@munigest.invalid", "a@b", "a b@example.com"]
)
def test_recovery_requires_deliverable_email(email):
    with pytest.raises(UserError):
        account_email(email)


@pytest.mark.parametrize(
    "value",
    [
        "https://kslzmrddrhfyyrxyfmbw.supabase.co/auth/v1/verify?type=recovery&token=" + "a" * 64,
        CONFIG.url + "/auth/v1/verify?type=signup&token=" + "a" * 64,
        CONFIG.url + "/auth/v1/verify?type=recovery&token=" + "a" * 64 + "&token=" + "b" * 64,
        "https://attacker.example/verify?token=123456",
        "123",
        "javascript:alert(1)",
    ],
)
def test_verification_refuses_foreign_or_wrong_purpose_links(value):
    with pytest.raises(UserError):
        verification_payload(value, "person@example.com", "recovery", CONFIG.url)


def test_verification_payload_and_password_validation():
    assert verification_payload("123456", " PERSON@example.com ", "signup", CONFIG.url) == {
        "email": "person@example.com",
        "token": "123456",
        "type": "signup",
    }
    with pytest.raises(UserError):
        new_password("123456", "123456")
    with pytest.raises(UserError):
        new_password("x" * 12, "y" * 12)


def test_recovery_updates_password_with_temporary_session_and_closes_it():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/verify"):
            assert json.loads(request.content)["type"] == "recovery"
            return httpx.Response(200, json={"access_token": "recovery-session"})
        assert request.headers["Authorization"] == "Bearer recovery-session"
        if request.url.path.endswith("/user"):
            assert json.loads(request.content) == {"password": "secure-new-password"}
        return httpx.Response(200, json={})

    async def run():
        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler))
        await repo.verify_account(
            "person@example.com", "123456", "recovery", "secure-new-password", "secure-new-password"
        )
        assert repo.session is None
        assert [r.url.path for r in requests] == [
            "/auth/v1/verify",
            "/auth/v1/user",
            "/auth/v1/logout",
        ]
        assert requests[-1].url.params["scope"] == "local"
        await repo.close()

    asyncio.run(run())


def test_failed_password_update_still_closes_temporary_session():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if paths[-1].endswith("verify"):
            return httpx.Response(200, json={"access_token": "temporary"})
        return httpx.Response(
            422 if paths[-1].endswith("user") else 200, json={"message": "private detail"}
        )

    async def run():
        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler))
        with pytest.raises(UserError) as exc:
            await repo.verify_account(
                "person@example.com",
                "123456",
                "recovery",
                "secure-new-password",
                "secure-new-password",
            )
        assert "private detail" not in str(exc.value)
        assert paths[-1].endswith("logout")
        await repo.close()

    asyncio.run(run())


def test_signup_only_sends_invitation_proof_not_roles():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["data"] == {"municipal_invitation": "a" * 64}
        return httpx.Response(200, json={"user": {"id": "pending"}})

    async def run():
        repo = SupabaseRepository(CONFIG, httpx.MockTransport(handler))
        assert not await repo.activate_account(
            "person@example.com", "a" * 64, "secure-new-password", "secure-new-password"
        )
        assert repo.session is None
        await repo.close()

    asyncio.run(run())


def test_account_forms_build_for_mobile_and_desktop():
    async def run():
        for width in [390, 1280]:
            page = PageStub()
            page.width = width
            app = MunicipalApp(page, replace(CONFIG, mode="demo"), DemoRepository())
            account = AccountScreen(app)
            for kind in ["signup", "confirm", "recovery"]:
                account.public_form(kind)
                for control in page.controls:
                    assert_valid_wrapping_layout(control)
            app.profile = await app.repo.sign_in()
            app.shell()
            await account.invitation_form()
            assert_valid_wrapping_layout(app.content)
            await app.close()

    asyncio.run(run())
