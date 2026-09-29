"""Compatibilidad del mismo cliente Python con Pyodide y sistemas nativos."""

import asyncio
import sys

import httpx


class BrowserTransport(httpx.AsyncBaseTransport):
    """Usa Fetch: los navegadores no permiten las conexiones TCP de HTTPX."""

    async def handle_async_request(self, request):
        from js import AbortController
        from pyodide.http import pyfetch

        controller = AbortController.new()
        headers = {
            key: value
            for key, value in request.headers.items()
            if key not in {"host", "content-length", "connection", "accept-encoding", "user-agent"}
        }
        options = {
            "method": request.method,
            "headers": headers,
            "credentials": "omit",
            "redirect": "error",
            "cache": "no-store",
            "signal": controller.signal,
        }
        if request.method not in {"GET", "HEAD"}:
            options["body"] = await request.aread()
        timeout = request.extensions.get("timeout", {}).get("read", 25)
        try:
            async with asyncio.timeout(timeout):
                response = await pyfetch(str(request.url), **options)
                content = await response.bytes()
            # Fetch ya descomprimió el cuerpo. Evitar una segunda descompresión.
            response_headers = {
                key: value
                for key, value in response.headers.items()
                if key.lower() not in {"content-encoding", "content-length"}
            }
            return httpx.Response(
                response.status, headers=response_headers, content=content, request=request
            )
        except TimeoutError as exc:
            raise httpx.ReadTimeout("El servidor no respondió a tiempo.", request=request) from exc
        except httpx.HTTPError:
            raise
        except Exception as exc:
            raise httpx.ConnectError(
                "No se pudo completar la solicitud web.", request=request
            ) from exc
        finally:
            controller.abort()


def browser_transport():
    return BrowserTransport() if sys.platform == "emscripten" else None


async def build_document(builder, data):
    # Pyodide no permite iniciar hilos; los documentos acotados se arman en memoria.
    if sys.platform == "emscripten":
        await asyncio.sleep(0)
        return builder(data)
    return await asyncio.to_thread(builder, data)
