"""Acciones relativas al Agente de IA."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bot_tv.actions.models import AgentTalkResult, ModelInfo
from bot_tv.agent.models import AVAILABLE_MODELS

if TYPE_CHECKING:
    from bot_tv.agent import TalkAgent
    from bot_tv.agent.rate_limiter import RateLimitStatus


def action_get_rpm_status(
    agent: TalkAgent, show_all: bool = False
) -> list[RateLimitStatus]:
    """Retorna el estado RPM del modelo activo o de todos los modelos."""
    if show_all:
        return agent.get_all_rpm_status()
    return [agent.get_rpm_status()]


def action_get_models() -> list[ModelInfo]:
    """Lista todos los modelos con sus límites y disponibilidad."""
    return [
        ModelInfo(
            name=name,
            display_name=cfg.display_name,
            enabled=cfg.enabled,
            rpm_limit=cfg.rpm_limit,
            rpd_limit=cfg.rpd_limit,
        )
        for name, cfg in AVAILABLE_MODELS.items()
    ]


def action_switch_model(agent: TalkAgent, model: str) -> str:
    """Cambia el modelo activo. Retorna mensaje descriptivo del resultado."""
    return agent.switch_model(model)


async def action_talk(agent: TalkAgent, message: str) -> AgentTalkResult:
    """Envía un mensaje al agente y retorna la respuesta y el modelo usado."""
    raw = await agent.chat(message)
    return AgentTalkResult(response=raw.strip(), model=agent.current_model)


def action_clear_agent_chat(agent: TalkAgent) -> None:
    """Limpia el historial conversacional del agente."""
    agent.clear_history()


async def action_set_context_limit(agent: TalkAgent, limit: int) -> None:
    """Establece y persiste el límite de contexto del agente."""
    await agent.set_context_limit(limit)
