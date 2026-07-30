"""Endpoints de la API REST relativos al Agente IA."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import Response

from bot_tv.actions.agent import (
    action_clear_agent_chat,
    action_get_models,
    action_get_rpm_status,
    action_set_context_limit,
    action_switch_model,
    action_talk,
)
from bot_tv.events import AgentResponseEvent
from bot_tv.web.api.helpers import _err, _ok, _parse_body

if TYPE_CHECKING:
    from bot_tv.agent import TalkAgent
    from bot_tv.bot import Bot


async def endpoint_switch_model(request: Request) -> Response:
    agent: TalkAgent = request.app.state.agent
    body = await _parse_body(request)
    model = body.get("model", "").strip()
    if not model:
        return _err("Campo 'model' requerido.")

    message = action_switch_model(agent, model)
    return _ok({"message": message, "current_model": agent.current_model})


async def endpoint_talk(request: Request) -> Response:
    agent: TalkAgent = request.app.state.agent
    bot: Bot = request.app.state.bot
    event_bus = bot.event_bus

    body = await _parse_body(request)
    message = body.get("message", "").strip()
    if not message:
        return _err("Campo 'message' requerido.")

    result = await action_talk(agent, message)

    await event_bus.emit(
        AgentResponseEvent(
            timestamp=datetime.now().isoformat(),
            question=message,
            response=result.response,
            model=result.model,
        )
    )

    return _ok({"response": result.response, "model": result.model})


async def endpoint_clear_agent_chat(request: Request) -> Response:
    """Limpia la memoria conversacional del agente."""
    agent: TalkAgent = request.app.state.agent
    action_clear_agent_chat(agent)
    return _ok({"message": "Historial de conversación limpiado."})


async def endpoint_set_context_limit(request: Request) -> Response:
    """Actualiza y persiste el límite de contexto del agente."""
    agent: TalkAgent = request.app.state.agent
    body = await _parse_body(request)
    limit_val = body.get("limit", 0)
    try:
        limit = max(0, int(limit_val))
    except ValueError, TypeError:
        return _err("El campo 'limit' debe ser un número entero >= 0.")

    await action_set_context_limit(agent, limit)
    return _ok(
        {
            "message": f"Límite de contexto actualizado a {limit}.",
            "context_limit": agent.context_limit,
        }
    )


async def endpoint_get_rpm(request: Request) -> Response:
    agent: TalkAgent = request.app.state.agent
    show_all = request.query_params.get("all", "").lower() in ("1", "true", "yes")
    statuses = action_get_rpm_status(agent, show_all)
    return _ok(
        {
            "context_limit": agent.context_limit,
            "statuses": [
                {
                    "model": s.model,
                    "display_name": s.display_name,
                    "rpm_used": s.rpm_used,
                    "rpm_limit": s.rpm_limit,
                    "rpd_used": s.rpd_used,
                    "rpd_limit": s.rpd_limit,
                    "is_blocked": s.is_blocked,
                    "blocked_reason": s.blocked_reason,
                    "next_slot_in": s.next_slot_in,
                }
                for s in statuses
            ],
        }
    )


async def endpoint_get_models(request: Request) -> Response:
    infos = action_get_models()
    return _ok(
        [
            {
                "name": m.name,
                "display_name": m.display_name,
                "enabled": m.enabled,
                "rpm_limit": m.rpm_limit,
                "rpd_limit": m.rpd_limit,
            }
            for m in infos
        ]
    )
