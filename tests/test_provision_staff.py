import json

import httpx
import pytest

from munigest.domain import UserError
from munigest.institution import INSTITUTION_NAME
from scripts.provision_staff import StaffProvisioner, main

KEY = "sb_secret_unit-test-value-not-a-real-key"
USER_ID = "aaaaaaaa-0000-4000-8000-000000000001"
DEPARTMENT_ID = "bbbbbbbb-0000-4000-8000-000000000001"
PERSON = {
    "email": "operador@municipal.test",
    "name": "Operador de prueba",
    "role": "consulta",
    "department": "MP",
}


class AdminAPI:
    def __init__(self):
        self.calls = []
        self.profile = None
        self.confirmed = True
        self.fail_profile = False
        self.race = False
        self.active_department = True

    def __call__(self, request):
        assert request.headers["apikey"] == KEY
        assert "Authorization" not in request.headers
        assert request.url.host == "lxvmwjcqdjoidgpinmgm.supabase.co"
        self.calls.append((request.method, request.url.path))
        path = request.url.path
        if path.endswith("municipal_settings"):
            return httpx.Response(200, json=[{"institution_name": INSTITUTION_NAME}])
        if path.endswith("departments"):
            rows = [{"id": DEPARTMENT_ID, "name": "Mesa de Partes"}]
            return httpx.Response(200, json=rows if self.active_department else [])
        if "/auth/v1/admin/users" in path:
            if request.method == "POST":
                body = json.loads(request.content)
                assert body["email_confirm"] is True
                assert "role" not in body["user_metadata"]
            return httpx.Response(
                200,
                json={
                    "id": USER_ID,
                    "email": PERSON["email"],
                    "email_confirmed_at": "2026-09-16T12:00:00Z" if self.confirmed else None,
                },
            )
        if path.endswith("staff_profiles"):
            if request.method == "POST":
                if self.fail_profile:
                    return httpx.Response(503, json={"message": KEY})
                assert "ignore-duplicates" in request.headers["Prefer"]
                self.profile = json.loads(request.content)
                if self.race:
                    self.profile["role"] = "gestor"
            return httpx.Response(200, json=[self.profile] if self.profile else [])
        raise AssertionError(f"Unexpected request: {request.method} {path}")


def client(api):
    return StaffProvisioner(KEY, transport=httpx.MockTransport(api))


@pytest.mark.parametrize("role", ["admin", "mesa_partes", "gestor", "consulta"])
def test_create_verified_person_and_read_back_profile(role):
    api = AdminAPI()
    provisioner = client(api)
    try:
        result = provisioner.provision(
            **{**PERSON, "role": role}, password="Individual-password-2026!", email_verified=True
        )
        assert result == (USER_ID, True)
        assert api.profile["role"] == role
        assert api.profile["department_id"] == DEPARTMENT_ID
        assert api.profile["is_active"] is True
        assert api.calls[-1] == ("GET", "/rest/v1/staff_profiles")
    finally:
        provisioner.close()


@pytest.mark.parametrize(
    "url,key",
    [
        ("https://kslzmrddrhfyyrxyfmbw.supabase.co", KEY),
        ("https://lxvmwjcqdjoidgpinmgm.supabase.co.evil.test", KEY),
        ("https://lxvmwjcqdjoidgpinmgm.supabase.co", "sb_publishable_not-admin"),
    ],
)
def test_reject_wrong_project_and_client_key_before_network(url, key):
    with pytest.raises(UserError):
        StaffProvisioner(key, url=url)


def test_create_requires_operator_email_verification_before_network():
    api = AdminAPI()
    provisioner = client(api)
    try:
        with pytest.raises(UserError, match="titularidad"):
            provisioner.provision(**PERSON, password="Individual-password-2026!")
        assert not api.calls
    finally:
        provisioner.close()


def test_inactive_department_does_not_create_auth_account():
    api = AdminAPI()
    api.active_department = False
    provisioner = client(api)
    try:
        with pytest.raises(UserError, match="desactivada"):
            provisioner.provision(
                **PERSON, password="Individual-password-2026!", email_verified=True
            )
        assert all(method == "GET" for method, _ in api.calls)
    finally:
        provisioner.close()


def test_existing_unconfirmed_identity_cannot_receive_access():
    api = AdminAPI()
    api.confirmed = False
    provisioner = client(api)
    try:
        with pytest.raises(UserError, match="confirmado"):
            provisioner.provision(**PERSON, user_id=USER_ID)
        assert all(method == "GET" for method, _ in api.calls)
    finally:
        provisioner.close()


def test_resume_is_idempotent_and_cannot_promote_existing_profile():
    api = AdminAPI()
    provisioner = client(api)
    try:
        provisioner.provision(**PERSON, user_id=USER_ID)
        api.calls.clear()
        assert provisioner.provision(**PERSON, user_id=USER_ID) == (USER_ID, False)
        assert all(method == "GET" for method, _ in api.calls)
        with pytest.raises(UserError, match="perfil diferente"):
            provisioner.provision(**{**PERSON, "role": "admin"}, user_id=USER_ID)
        assert api.profile["role"] == "consulta"
    finally:
        provisioner.close()


def test_partial_failure_preserves_auth_and_does_not_retry_or_leak_key():
    api = AdminAPI()
    api.fail_profile = True
    provisioner = client(api)
    try:
        with pytest.raises(UserError) as error:
            provisioner.provision(
                **PERSON, password="Individual-password-2026!", email_verified=True
            )
        assert USER_ID in str(error.value)
        assert "--user-id" in str(error.value)
        assert KEY not in str(error.value)
        assert api.calls.count(("POST", "/auth/v1/admin/users")) == 1
        assert all(method != "DELETE" for method, _ in api.calls)
    finally:
        provisioner.close()


def test_concurrent_profile_change_is_reported_without_overwrite():
    api = AdminAPI()
    api.race = True
    provisioner = client(api)
    try:
        with pytest.raises(UserError, match="no coincide"):
            provisioner.provision(**PERSON, user_id=USER_ID)
        assert api.profile["role"] == "gestor"
        assert all(method != "PATCH" for method, _ in api.calls)
    finally:
        provisioner.close()


def test_preview_does_not_need_credentials_or_open_connection(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    assert (
        main(
            [
                "--email",
                "persona@example.com",
                "--name",
                "Persona de ejemplo",
                "--role",
                "consulta",
                "--department",
                "MP",
            ]
        )
        == 0
    )
    assert "No se conectó" in capsys.readouterr().out
