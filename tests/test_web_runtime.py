import asyncio
import sys
from types import SimpleNamespace

import httpx
import pytest

from munigest import web_runtime


@pytest.fixture
def browser(monkeypatch):
    calls = []
    controller = SimpleNamespace(signal=object(), abort=lambda: calls.append("abort"))
    monkeypatch.setitem(
        sys.modules, "js", SimpleNamespace(AbortController=SimpleNamespace(new=lambda: controller))
    )

    async def fetch(url, **options):
        calls.append((url, options))

        async def content():
            return b'{"ok":true}'

        return SimpleNamespace(
            status=200,
            headers={"content-type": "application/json", "content-encoding": "gzip"},
            bytes=content,
        )

    module = SimpleNamespace(pyfetch=fetch)
    monkeypatch.setitem(sys.modules, "pyodide", SimpleNamespace(http=module))
    monkeypatch.setitem(sys.modules, "pyodide.http", module)
    return calls, module


def test_fetch_keeps_auth_query_and_binary_payload_without_redirects(browser):
    calls, _ = browser

    async def exercise():
        async with httpx.AsyncClient(transport=web_runtime.BrowserTransport()) as client:
            result = await client.post(
                "https://project.supabase.co/storage/v1/object/file",
                params={"name": "oficio público"},
                headers={"Authorization": "Bearer test-token", "apikey": "public-key"},
                content=b"%PDF-1.4\x00\xff",
            )
            assert result.json() == {"ok": True}

    asyncio.run(exercise())
    url, options = calls[0]
    assert "oficio+p%C3%BAblico" in url
    assert options["body"] == b"%PDF-1.4\x00\xff"
    assert options["headers"]["authorization"] == "Bearer test-token"
    assert options["headers"]["apikey"] == "public-key"
    assert "host" not in options["headers"]
    assert "content-length" not in options["headers"]
    assert options["credentials"] == "omit"
    assert options["redirect"] == "error"
    assert calls[-1] == "abort"


@pytest.mark.parametrize("failure", ["network", "timeout"])
def test_fetch_failures_are_httpx_errors_and_abort_the_request(browser, failure):
    calls, module = browser

    async def broken(*args, **kwargs):
        if failure == "timeout":
            await asyncio.sleep(1)
        raise TypeError("Failed to fetch")

    module.pyfetch = broken

    async def exercise():
        async with httpx.AsyncClient(
            transport=web_runtime.BrowserTransport(), timeout=0.001
        ) as client:
            with pytest.raises(httpx.ReadTimeout if failure == "timeout" else httpx.ConnectError):
                await client.get("https://project.supabase.co/rest/v1/cases")

    asyncio.run(exercise())
    assert calls == ["abort"]


def test_web_documents_do_not_start_threads(monkeypatch):
    monkeypatch.setattr(web_runtime.sys, "platform", "emscripten")

    async def forbidden(*args):
        pytest.fail("El navegador no puede iniciar hilos.")

    monkeypatch.setattr(web_runtime.asyncio, "to_thread", forbidden)
    assert (
        asyncio.run(web_runtime.build_document(lambda value: b"%PDF-" + value, b"1.4"))
        == b"%PDF-1.4"
    )
    assert isinstance(web_runtime.browser_transport(), web_runtime.BrowserTransport)
