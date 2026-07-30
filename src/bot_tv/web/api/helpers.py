"""Helpers HTTP para los endpoints de la API REST."""

from __future__ import annotations

import contextlib
import json

from starlette.requests import Request
from starlette.responses import JSONResponse


def _ok(data: object = None) -> JSONResponse:
    return JSONResponse({"ok": True, "data": data})


def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


async def _parse_body(request: Request) -> dict:
    """Parsea el body JSON de la request. Retorna dict vacío si no hay body."""
    with contextlib.suppress(json.JSONDecodeError, UnicodeDecodeError):
        body = await request.body()
        if body:
            return json.loads(body)  # type: ignore[return-value]
    return {}
