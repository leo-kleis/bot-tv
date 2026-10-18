"""Helpers HTTP para los endpoints de la API REST."""

from __future__ import annotations

import contextlib
import json
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 65536


def _ok(data: object = None) -> JSONResponse:
    return JSONResponse({"ok": True, "data": data})


def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


def _get_str(body: dict[str, Any], key: str, default: str = "") -> str:
    """Extrae de forma segura un string con strip desde el diccionario del body."""
    val = body.get(key, default)
    return val.strip() if isinstance(val, str) else default


def _parse_int_param(
    request: Request,
    name: str,
    default: int,
    *,
    min_val: int = 1,
    max_val: int = 500,
) -> int:
    """Parsea un query param entero y lo acota al rango [min_val, max_val]."""
    raw = request.query_params.get(name)
    if raw is None or not raw.strip():
        return max(min_val, min(max_val, default))
    val = int(raw.strip())
    return max(min_val, min(max_val, val))


async def _parse_body(
    request: Request, max_bytes: int = MAX_BODY_BYTES
) -> dict[str, Any]:
    """Parsea el body JSON de la request validando Content-Type, tamaño y estructura."""
    content_length = request.headers.get("content-length")
    if content_length:
        with contextlib.suppress(ValueError):
            if int(content_length) > max_bytes:
                return {}

    with contextlib.suppress(json.JSONDecodeError, UnicodeDecodeError):
        body = await request.body()
        if not body or len(body) > max_bytes:
            return {}
        content_type = request.headers.get("content-type", "").lower()
        if not content_type.startswith("application/json"):
            return {}
        data = json.loads(body)
        if isinstance(data, dict):
            return data
    return {}
