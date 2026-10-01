"""Endpoints REST para el audio keep-alive del host."""

from __future__ import annotations

import asyncio

from starlette.requests import Request
from starlette.responses import JSONResponse

from bot_tv.utils.audio_keepalive import AUDIO_KEEP_ALIVE
from bot_tv.web.api.helpers import _err, _ok, _parse_body


async def endpoint_get_audio_keepalive(_request: Request) -> JSONResponse:
    """Retorna el estado y configuración actual del audio keep-alive."""
    return _ok(AUDIO_KEEP_ALIVE.get_status())


async def endpoint_set_audio_keepalive(request: Request) -> JSONResponse:
    """Actualiza la configuración o estado activo del audio keep-alive."""
    body = await _parse_body(request)
    if "enabled" not in body:
        return _err("El campo 'enabled' es requerido.", 400)

    enabled = bool(body["enabled"])
    volume = body.get("volume")
    frequency = body.get("frequency")

    status = AUDIO_KEEP_ALIVE.update_settings(
        enabled=enabled,
        volume=float(volume) if volume is not None else None,
        frequency=float(frequency) if frequency is not None else None,
    )
    return _ok(status)


async def endpoint_test_audio_keepalive(_request: Request) -> JSONResponse:
    """Emite un tono breve de prueba en el PC anfitrión."""
    success = await asyncio.to_thread(AUDIO_KEEP_ALIVE.test_beep)
    if success:
        return _ok({"tested": True})
    return _err("No se pudo reproducir el sonido de prueba en el host.", 500)
