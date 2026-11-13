"""Helpers HTTP para los endpoints de la API REST."""

from __future__ import annotations

import contextlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 65536


def _serialize(obj: Any) -> Any:
    """Serializa recursivamente estructuras para JSON seguro."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _ok(data: object = None) -> JSONResponse:
    return JSONResponse({"ok": True, "data": _serialize(data)})


def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


def _json_ok(data: Any = None) -> JSONResponse:
    """Genera respuesta JSON estandarizada con código 200 y serialización segura."""
    return _ok(data)


def _json_err(message: str, status_code: int = 400) -> JSONResponse:
    """Genera respuesta JSON estandarizada de error."""
    return _err(message, status=status_code)


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
    max_val: int | None = 500,
    strict_min: bool = False,
) -> int | JSONResponse:
    """Parsea un query param entero y retorna error 400 si no es válido."""
    raw = request.query_params.get(name)
    if raw is None or not raw.strip():
        clamped = max(min_val, default)
        return min(max_val, clamped) if max_val is not None else clamped

    try:
        val = int(raw.strip())
    except ValueError:
        return _err(
            f"El parámetro '{name}' debe ser un número entero válido.",
            status=400,
        )

    if strict_min and val < min_val:
        return _err(
            f"El parámetro '{name}' debe ser un número entero >= {min_val}.",
            status=400,
        )

    clamped = max(min_val, val)
    return min(max_val, clamped) if max_val is not None else clamped


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
