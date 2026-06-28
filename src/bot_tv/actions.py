"""Acciones compartidas del bot.

Lógica pura sin presentación. Usada tanto por el REPL de terminal
(console/commands.py) como por la REST API de bot-web (web/api.py).
Cada función retorna datos tipados que cada consumer formatea a su modo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import twitchio

from bot_tv.agent.models import AVAILABLE_MODELS
from bot_tv.agent.rate_limiter import RateLimitStatus
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
class UserRolesResult:
    """Resultado de actualizar los roles de un usuario."""

    username: str
    user_id: str
    is_bot: bool
    is_moderator: bool
    is_vip: bool
    is_subscriber: bool


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

    user_id = await bot.user_repo.get_user_id_by_name(username)
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
        await bot.user_repo.upsert_user(
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
    user_id = await bot.user_repo.get_user_id_by_name(username.lower())
    if not user_id:
        return f"El usuario '{username}' no existe en la base de datos."

    es_bot = await bot.user_repo.is_user_bot(user_id)
    await bot.user_repo.set_user_bot(user_id, not es_bot)
    return BotToggleResult(
        username=username,
        is_bot=not es_bot,
        user_id=user_id,
    )


async def action_set_nickname(
    bot: Bot, username: str, nickname: str | None
) -> NicknameResult | str:
    """Asigna o elimina el apodo de un usuario."""
    user_id = await bot.user_repo.get_user_id_by_name(username.lower())
    if not user_id:
        return f"El usuario '{username}' no existe en la base de datos."

    await bot.user_repo.set_nickname(user_id, nickname)
    return NicknameResult(username=username, nickname=nickname)


async def action_update_user_roles(
    bot: Bot,
    username: str,
    is_bot: bool,
    is_moderator: bool,
    is_vip: bool,
) -> UserRolesResult | str:
    """Actualiza los roles de un usuario en Twitch y en la DB."""
    import logging

    logger = logging.getLogger(__name__)

    user_id = await bot.user_repo.get_user_id_by_name(username.lower())
    if not user_id:
        # Intentar buscarlo en Twitch si no está en la base de datos local
        try:
            twitch_user = await bot.fetch_user(login=username)
            if not twitch_user:
                return (
                    f"El usuario '{username}' no existe en Twitch "
                    "ni en la base de datos."
                )
            user_id = twitch_user.id
            await bot.user_repo.upsert_user(
                user_id,
                twitch_user.name or username,
                twitch_user.display_name,
            )
        except Exception as e:
            logger.exception("Error al buscar usuario en Twitch: %s", e)
            return f"Error al buscar al usuario '{username}' en Twitch: {e}"

    # Evitar cambiar roles al broadcaster
    channels = await bot.get_channels()
    if not channels:
        return "No hay canales configurados."
    broadcaster_id = channels[0]["user_id"]

    if user_id == broadcaster_id:
        return "No se pueden modificar los roles del broadcaster."

    # Obtener roles actuales
    current_roles = await bot.user_repo.get_user_roles(user_id)
    current_mod = current_roles.get("is_moderator", False) if current_roles else False
    current_vip = current_roles.get("is_vip", False) if current_roles else False
    current_sub = current_roles.get("is_subscriber", False) if current_roles else False

    # Actualizar en Twitch Helix a nombre del broadcaster
    broadcaster = twitchio.PartialUser(id=broadcaster_id, http=bot._http)

    # 1. Ejecutar las remociones primero para evitar conflictos de exclusión mutua
    # Remoción de Moderador
    if not is_moderator and current_mod:
        try:
            await broadcaster.remove_moderator(user=user_id)
        except twitchio.HTTPException as e:
            logger.error("Error al quitar moderador para %s en Twitch: %s", username, e)
            if e.status in (401, 403):
                return (
                    "Error de permisos en Twitch. Asegúrate de tener los tokens "
                    "del Broadcaster autorizados con los permisos de moderación."
                )
            msg_twitch = e.extra.get("message") if isinstance(e.extra, dict) else str(e)
            return f"Error de Twitch al quitar moderación: {msg_twitch}"

    # Remoción de VIP
    if not is_vip and current_vip:
        try:
            await broadcaster.remove_vip(user=user_id)
        except twitchio.HTTPException as e:
            logger.error("Error al quitar VIP para %s en Twitch: %s", username, e)
            if e.status in (401, 403):
                return (
                    "Error de permisos en Twitch. Asegúrate de tener los tokens "
                    "del Broadcaster autorizados con los permisos de VIP."
                )
            msg_twitch = e.extra.get("message") if isinstance(e.extra, dict) else str(e)
            return f"Error de Twitch al quitar VIP: {msg_twitch}"

    # 2. Ejecutar las adiciones después
    # Adición de Moderador
    if is_moderator and not current_mod:
        try:
            await broadcaster.add_moderator(user=user_id)
        except twitchio.HTTPException as e:
            logger.error(
                "Error al agregar moderador para %s en Twitch: %s", username, e
            )
            if e.status in (401, 403):
                return (
                    "Error de permisos en Twitch. Asegúrate de tener los tokens "
                    "del Broadcaster autorizados con los permisos de moderación."
                )
            msg_twitch = e.extra.get("message") if isinstance(e.extra, dict) else str(e)
            if msg_twitch and "vip of this channel" in msg_twitch.lower():
                return (
                    "El usuario ya es VIP del canal y no puede ser moderador "
                    "al mismo tiempo."
                )
            return f"Error de Twitch al agregar moderador: {msg_twitch}"

    # Adición de VIP
    if is_vip and not current_vip:
        try:
            await broadcaster.add_vip(user=user_id)
        except twitchio.HTTPException as e:
            logger.error("Error al agregar VIP para %s en Twitch: %s", username, e)
            if e.status in (401, 403):
                return (
                    "Error de permisos en Twitch. Asegúrate de tener los tokens "
                    "del Broadcaster autorizados con los permisos de VIP."
                )
            msg_twitch = e.extra.get("message") if isinstance(e.extra, dict) else str(e)
            if msg_twitch and "moderator of this channel" in msg_twitch.lower():
                return (
                    "El usuario ya es moderador del canal y no puede ser VIP "
                    "al mismo tiempo."
                )
            return f"Error de Twitch al agregar VIP: {msg_twitch}"

    # Actualizar en la base de datos local
    await bot.user_repo.update_user_roles(
        user_id=user_id,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
    )

    return UserRolesResult(
        username=username,
        user_id=user_id,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
        is_subscriber=current_sub,
    )


async def action_sync_user_roles(
    bot: Bot,
    username: str,
) -> UserRolesResult | str:
    """Consulta Twitch para sincronizar los roles actuales de un usuario."""
    import logging

    import twitchio

    logger = logging.getLogger(__name__)

    user_id = await bot.user_repo.get_user_id_by_name(username.lower())
    if not user_id:
        # Intentar resolver en Twitch
        try:
            twitch_user = await bot.fetch_user(login=username)
            if not twitch_user:
                return f"El usuario '{username}' no existe en Twitch."
            user_id = twitch_user.id
            await bot.user_repo.upsert_user(
                user_id,
                twitch_user.name or username,
                twitch_user.display_name,
            )
        except Exception as e:
            logger.exception("Error al buscar usuario en Twitch: %s", e)
            return f"Error al buscar al usuario '{username}' en Twitch: {e}"

    # Obtener el broadcaster actual
    channels = await bot.get_channels()
    if not channels:
        return "No hay canales configurados."
    broadcaster_id = channels[0]["user_id"]

    # Obtener token de acceso del broadcaster de la base de datos de tokens
    async with bot.token_database.acquire() as conn:
        row = await conn.fetchone(
            "SELECT token FROM tokens WHERE user_id = ?",
            (broadcaster_id,),
        )
    if not row:
        return "No se encontró el token de acceso del Broadcaster."
    broadcaster_token = str(row["token"])

    # Si es el broadcaster, tiene todos los roles excepto bot por defecto
    if user_id == broadcaster_id:
        # Asegurarse de que esté correcto en DB
        await bot.user_repo.update_user_roles(
            user_id=user_id,
            is_bot=False,
            is_moderator=True,
            is_vip=False,
        )
        return UserRolesResult(
            username=username,
            user_id=user_id,
            is_bot=False,
            is_moderator=True,
            is_vip=False,
            is_subscriber=True,
        )

    # Obtener roles locales actuales por si falla la sincronización de algún rol
    current_roles = await bot.user_repo.get_user_roles(user_id)
    current_mod = current_roles.get("is_moderator", False) if current_roles else False
    current_vip = current_roles.get("is_vip", False) if current_roles else False
    current_sub = current_roles.get("is_subscriber", False) if current_roles else False

    # Inicializar estado con los valores locales por defecto
    is_moderator = current_mod
    is_vip = current_vip
    is_subscriber = current_sub

    broadcaster = twitchio.PartialUser(id=broadcaster_id, http=bot._http)

    # 1. Comprobar Moderador
    try:
        # fetch_moderators devuelve la lista completa
        moderators = await broadcaster.fetch_moderators()
        is_moderator = any(m.id == user_id for m in moderators)
    except twitchio.HTTPException as e:
        logger.warning(
            "No se pudieron sincronizar moderadores de Twitch para %s (HTTP %s): %s",
            username,
            e.status,
            e,
        )

    # 2. Comprobar VIP
    try:
        # fetch_vips acepta user_ids como filtro
        vips = await broadcaster.fetch_vips(user_ids=[user_id])
        is_vip = any(v.id == user_id for v in vips)
    except twitchio.HTTPException as e:
        logger.warning(
            "No se pudieron sincronizar VIPs de Twitch para %s (HTTP %s): %s",
            username,
            e.status,
            e,
        )

    # 3. Comprobar Suscriptor
    try:
        import aiohttp

        from bot_tv.utils.env import CLIENT_ID

        headers = {
            "Client-Id": CLIENT_ID,
            "Authorization": f"Bearer {broadcaster_token}",
        }
        params = {
            "broadcaster_id": broadcaster_id,
            "user_id": user_id,
        }
        async with (
            aiohttp.ClientSession() as session,
            session.get(
                "https://api.twitch.tv/helix/subscriptions/user",
                headers=headers,
                params=params,
            ) as resp,
        ):
            if resp.status == 200:
                data = await resp.json()
                is_subscriber = bool(data and data.get("data"))
            elif resp.status == 404:
                is_subscriber = False
            elif resp.status in (401, 403):
                logger.warning(
                    "No se pudo comprobar la suscripción para %s (HTTP %s): "
                    "la cuenta Broadcaster podría no ser afiliada/partner o "
                    "falta el scope de suscripciones.",
                    username,
                    resp.status,
                )
            else:
                body_text = await resp.text()
                logger.warning(
                    "Error al obtener suscripción de Twitch para %s (HTTP %s): %s",
                    username,
                    resp.status,
                    body_text,
                )
    except Exception as e:
        logger.warning(
            "Error inesperado al comprobar suscripción para %s: %s",
            username,
            e,
        )

    # Mantener el rol de bot actual en base de datos
    current_roles = await bot.user_repo.get_user_roles(user_id)
    is_bot = current_roles.get("is_bot", False) if current_roles else False

    # Actualizar en base de datos local (incluyendo is_subscriber)
    query_update = """
        UPDATE users
        SET is_moderator = ?,
            is_vip = ?,
            is_subscriber = ?
        WHERE user_id = ?
    """
    async with bot.user_repo._db.acquire() as conn:
        await conn.execute(
            query_update,
            (
                int(is_moderator),
                int(is_vip),
                int(is_subscriber),
                user_id,
            ),
        )

    return UserRolesResult(
        username=username,
        user_id=user_id,
        is_bot=is_bot,
        is_moderator=is_moderator,
        is_vip=is_vip,
        is_subscriber=is_subscriber,
    )


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
        await component.hacer_clip(raise_on_error=True)
        result = await asyncio.wait_for(future, timeout=15)
    except TimeoutError:
        result = "Timeout: el clip tardó demasiado."
    except Exception as e:
        msg = str(e) or "Fallo al crear el clip en Twitch"
        result = f"Error al crear el clip: {msg}"
    finally:
        bot.event_bus.emit = original_emit  # type: ignore[assignment]

    return result
