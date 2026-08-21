from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from bot_tv.events import ChatMessageEvent
from bot_tv.utils.colors import get_chatter_rgb

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


class ChatComponent(commands.Component):
    """Componente de chat: mensajes en consola + comandos generales."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._verified_avatars: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    def _get_chatter_role_cached(self, user_id: str, broadcaster_id: str | int) -> str:
        """Determina el rol del chatter de forma instantánea usando UserMemoryCache."""
        user_id_str = user_id
        broadcaster_id_str = str(broadcaster_id)

        if user_id_str == broadcaster_id_str:
            return "Broadcaster"

        if user_id_str == self.bot.bot_id:
            return "Bot"

        if self.bot.user_cache.is_user_bot(user_id_str):
            return "Bot"

        roles = self.bot.user_cache.get_user_roles(user_id_str, broadcaster_id_str)
        if roles and roles.get("followed_at") and not roles.get("unfollowed_at"):
            followed_at_iso = roles.get("followed_at")
            try:
                clean_str = followed_at_iso.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_str).astimezone()
                return dt.strftime("%d/%m/%y")
            except Exception:
                return "Visita"

        return "Visita"

    async def _enrich_and_persist(
        self,
        payload: twitchio.ChatMessage,
        user_id: str,
        username: str,
        display_name: str,
        msg_id: str | None,
        es_bot: bool,
    ) -> None:
        """Persiste datos en PostgreSQL y enriquece avatar/follow en segundo plano."""
        cache = self.bot.user_cache
        chatter = payload.chatter
        broadcaster_id = payload.broadcaster.id

        try:
            await self.bot.user_repo.upsert_user(
                user_id,
                username,
                display_name,
                cache=cache,
            )

            await self.bot.channel_user_repo.upsert_channel_user_roles(
                broadcaster_id,
                user_id,
                is_moderator=chatter.moderator,
                is_vip=chatter.vip,
                is_subscriber=chatter.subscriber,
                cache=cache,
            )

            if not es_bot:
                await self.bot.chat_repo.save_chat_message(
                    broadcaster_id,
                    user_id,
                    payload.text,
                    msg_id=msg_id,
                )

            # Verificar avatar si aún no se tiene
            profile_image_url = cache.get_profile_image_url(user_id)
            if profile_image_url is None or user_id not in self._verified_avatars:
                try:
                    fetched_users = await self.bot.fetch_users(ids=[int(user_id)])
                    if fetched_users:
                        profile_image = fetched_users[0].profile_image
                        if profile_image:
                            new_url = profile_image.url
                            if new_url != profile_image_url:
                                await self.bot.user_repo.set_profile_image_url(
                                    user_id, new_url, cache=cache
                                )
                            self._verified_avatars.add(user_id)
                except Exception:
                    LOGGER.debug("No se pudo obtener avatar para user_id=%s", user_id)

            # Verificar follow_info si no está en caché
            cached_roles = cache.get_user_roles(user_id, broadcaster_id)
            if not cached_roles or not cached_roles.get("followed_at"):
                try:
                    follow = await chatter.follow_info()
                    if follow and follow.followed_at:
                        await self.bot.channel_user_repo.upsert_channel_user_roles(
                            broadcaster_id,
                            user_id,
                            is_moderator=chatter.moderator,
                            is_vip=chatter.vip,
                            is_subscriber=chatter.subscriber,
                            cache=cache,
                        )
                except Exception:
                    LOGGER.debug(
                        "No se pudo consultar follow_info para user_id=%s", user_id
                    )

        except Exception:
            LOGGER.exception(
                "Error en enriquecimiento de mensaje en background para %s", username
            )

    @commands.Component.listener()
    async def event_message(self, payload: twitchio.ChatMessage) -> None:
        """Emite ChatMessageEvent de inmediato y delega la persistencia a background."""
        chatter = payload.chatter
        user_id = chatter.id
        username = chatter.name or user_id
        display_name = chatter.display_name or username
        cache = self.bot.user_cache
        msg_id = getattr(payload, "id", None)

        es_bot = (user_id == self.bot.bot_id) or cache.is_user_bot(user_id)
        nickname = cache.get_user_nickname(user_id)
        profile_image_url = cache.get_profile_image_url(user_id)

        hex_str = chatter.color.hex if chatter.color else None
        r, g, b = get_chatter_rgb(hex_str, username)

        role = self._get_chatter_role_cached(user_id, payload.broadcaster.id)

        # Extraer emotes nativos de Twitch desde los fragments del mensaje
        twitch_emotes: list[dict[str, str]] = []
        if hasattr(payload, "fragments"):
            for frag in payload.fragments:
                if frag.type == "emote" and frag.emote:
                    twitch_emotes.append({"id": frag.emote.id, "text": frag.text})

        # Emisión inmediata al EventBus (latencia < 1ms)
        await self.bot.event_bus.emit(
            ChatMessageEvent(
                id=msg_id,
                timestamp=datetime.now().isoformat(),
                user_id=user_id,
                username=username,
                display_name=display_name,
                nickname=nickname,
                color_rgb=(r, g, b),
                role=role,
                text=payload.text,
                channel_id=payload.broadcaster.id,
                is_bot=es_bot,
                emotes=twitch_emotes,
                profile_image_url=profile_image_url,
            )
        )

        # Delegar persistencia y llamadas externas a tarea asíncrona
        task = asyncio.create_task(
            self._enrich_and_persist(
                payload=payload,
                user_id=user_id,
                username=username,
                display_name=display_name,
                msg_id=msg_id,
                es_bot=es_bot,
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @commands.command()
    async def hola(self, ctx: commands.Context) -> None:
        """Saluda al usuario que invoca el comando.  ?hola"""
        await ctx.reply(f"¡Hola {ctx.chatter}!")

    @commands.command()
    async def eleccion(self, ctx: commands.Context, *opciones: str) -> None:
        """Elige aleatoriamente entre las opciones dadas.  ?eleccion <a> <b> ..."""
        await ctx.reply(
            f"Elegí: {random.choice(opciones)}" if opciones else "Dame opciones!"
        )

    async def component_command_error(
        self, payload: commands.CommandErrorPayload
    ) -> None:
        """Captura errores de comandos dentro de este componente."""
        error = payload.exception
        ctx = payload.context

        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            LOGGER.warning(
                "Faltan argumentos o son inválidos en '?%s': %s",
                ctx.command.name if ctx.command else "?",
                error,
            )
            return

        LOGGER.exception(
            "Error no manejado en '?%s'",
            ctx.command.name if ctx.command else "?",
            exc_info=error,
        )
