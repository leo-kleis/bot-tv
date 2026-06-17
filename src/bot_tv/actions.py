"""Acciones compartidas del bot.

Lógica pura sin presentación. Usada tanto por el REPL de terminal
(console/commands.py) como por la REST API de bot-web (web/api.py).
Cada función retorna datos tipados que cada consumer formatea a su modo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bot_tv.agent.models import AVAILABLE_MODELS
from bot_tv.agent.rate_limiter import RateLimitStatus
from bot_tv.database.app import (
    get_user_id_by_name,
    is_user_bot,
    set_nickname,
    set_user_bot,
    upsert_user,
)
from bot_tv.events import ClipCreatedEvent

if TYPE_CHECKING:
    from bot_tv.agent import TalkAgent
    from bot_tv.bot import Bot


# ── Tipos de retorno ─────────────────────────────────────────────────────────


@dataclass
class UserResolveResult:
    """Resultado de la resolución de un usuario."""

    user_id: str | None
    found_locally: bool
    found_on_twitch: bool
    error: str | None = None


@dataclass
class BotToggleResult:
    """Resultado de marcar/desmarcar un usuario como bot."""

    username: str
    is_bot: bool  # estado NUEVO (después del toggle)
    user_id: str


@dataclass
class NicknameResult:
    """Resultado de asignar/eliminar un apodo."""

    username: str
    nickname: str | None  # None = eliminado


@dataclass
class SyncFollowersResult:
    """Resultado de una sincronización de seguidores."""

    channel: str
    ok: bool
    error: str | None = None


@dataclass
class ModelInfo:
    """Info de un modelo disponible."""

    name: str
    display_name: str
    enabled: bool
    rpm_limit: int
    rpd_limit: int


@dataclass
class AgentTalkResult:
    """Resultado de una consulta al agente."""

    response: str
    model: str


# ── Resolución de usuarios ───────────────────────────────────────────────────


async def resolve_user(bot: Bot, username: str) -> UserResolveResult:
    """Busca user_id en DB local; si no está, consulta la API de Twitch."""
    import logging

    logger = logging.getLogger(__name__)

    user_id = await get_user_id_by_name(bot.app_database, username)
    if user_id:
        return UserResolveResult(
            user_id=user_id, found_locally=True, found_on_twitch=False
        )

    try:
        twitch_user = await bot.fetch_user(login=username)
        if not twitch_user:
            return UserResolveResult(
                user_id=None,
                found_locally=False,
                found_on_twitch=False,
                error=f"Usuario '{username}' no encontrado en Twitch.",
            )

        user_id = twitch_user.id
        await upsert_user(
            bot.app_database,
            user_id,
            twitch_user.name or username,
            twitch_user.display_name,
        )
        return UserResolveResult(
            user_id=user_id, found_locally=False, found_on_twitch=True
        )
    except Exception as e:
        logger.exception("Error al buscar usuario en Twitch.")
        return UserResolveResult(
            user_id=None,
            found_locally=False,
            found_on_twitch=False,
            error=str(e),
        )


# ── Acciones de usuario ──────────────────────────────────────────────────────


async def action_toggle_bot(bot: Bot, username: str) -> BotToggleResult | str:
    """Marca/desmarca un usuario como bot. Retorna BotToggleResult o string de error."""
    result = await resolve_user(bot, username.lower())
    if not result.user_id:
        return result.error or f"Usuario '{username}' no encontrado."

    es_bot = await is_user_bot(bot.app_database, result.user_id)
    await set_user_bot(bot.app_database, result.user_id, not es_bot)
    return BotToggleResult(
        username=username,
        is_bot=not es_bot,
        user_id=result.user_id,
    )


async def action_set_nickname(
    bot: Bot, username: str, nickname: str | None
) -> NicknameResult | str:
    """Asigna o elimina el apodo de un usuario."""
    result = await resolve_user(bot, username.lower())
    if not result.user_id:
        return result.error or f"Usuario '{username}' no encontrado."

    await set_nickname(bot.app_database, result.user_id, nickname)
    return NicknameResult(username=username, nickname=nickname)


# ── Acciones de seguidores ───────────────────────────────────────────────────


async def action_sync_followers(bot: Bot) -> list[SyncFollowersResult]:
    """Sincroniza seguidores de todos los canales. Retorna un resultado por canal."""
    import logging

    from bot_tv.components.followers_component import FollowersComponent

    logger = logging.getLogger(__name__)
    channels = await bot.get_channels()
    # pyrefly: ignore [missing-attribute]
    component = bot._components.get("FollowersComponent")

    results: list[SyncFollowersResult] = []

    if not isinstance(component, FollowersComponent):
        logger.error("Componente FollowersComponent no encontrado.")
        for channel in channels:
            results.append(
                SyncFollowersResult(
                    channel=channel["username"],
                    ok=False,
                    error="Componente no disponible.",
                )
            )
        return results

    for channel in channels:
        try:
            await component.check_and_sync(channel["user_id"])
            results.append(SyncFollowersResult(channel=channel["username"], ok=True))
        except Exception as e:
            logger.exception(
                "Error al sincronizar seguidores de %s", channel["username"]
            )
            results.append(
                SyncFollowersResult(channel=channel["username"], ok=False, error=str(e))
            )

    return results


# ── Acciones del agente ──────────────────────────────────────────────────────


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
    """Envía un mensaje al agente y retorna la respuesta limpia y el modelo usado."""
    raw = await agent.chat(message)

    # Limpiar marcas de formato Markdown
    cleaned = re.sub(r"\*\*|__", "", raw)
    cleaned = re.sub(r"\*|_", "", cleaned)
    cleaned = re.sub(r"`", "", cleaned)

    return AgentTalkResult(response=cleaned, model=agent.current_model)


# ── Ciclo de vida ────────────────────────────────────────────────────────────


async def action_exit(bot: Bot) -> None:
    """Cierra el bot limpiamente."""
    await bot.close()


async def action_create_clip(bot: Bot) -> ClipCreatedEvent | str:
    """Dispara la creación de un clip vía el ClipComponent y espera el resultado."""
    import asyncio
    import logging

    from bot_tv.components.clip_component import ClipComponent
    from bot_tv.events import ClipCreatedEvent as _ClipEvent

    logger = logging.getLogger(__name__)

    # pyrefly: ignore [missing-attribute]
    component = bot._components.get("ClipComponent")
    if not isinstance(component, ClipComponent):
        logger.error("ClipComponent no encontrado.")
        return "Componente ClipComponent no disponible."

    future: asyncio.Future[_ClipEvent | str] = asyncio.get_event_loop().create_future()

    original_emit = bot.event_bus.emit

    async def capture_and_restore(event: object) -> None:
        if isinstance(event, _ClipEvent) and not future.done():
            future.set_result(event)
        await original_emit(event)

    bot.event_bus.emit = capture_and_restore  # type: ignore[assignment]

    try:
        await component.hacer_clip()
        result = await asyncio.wait_for(future, timeout=15)
    except TimeoutError:
        result = "Timeout: el clip tardó demasiado."
    except Exception as e:
        result = str(e)
    finally:
        bot.event_bus.emit = original_emit  # type: ignore[assignment]

    return result
