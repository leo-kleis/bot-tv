from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from bot_tv.database.app import (
    get_user_nickname,
    is_user_bot,
    save_chat_message,
    upsert_user,
)
from bot_tv.events import ChatMessageEvent
from bot_tv.utils.colors import get_chatter_rgb

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


class ChatComponent(commands.Component):
    """Componente de chat: mensajes en consola + comandos generales."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def _get_chatter_role(
        self, chatter: twitchio.Chatter, broadcaster_id: str | int
    ) -> str:
        """Determina el rol del chatter como string limpio (sin markup Rich).

        Prioridad:
        1. Broadcaster → 'Broadcaster'
        2. Nuestro bot → 'Bot'
        3. Bot marcado en DB → 'Bot'
        4. Seguidor → 'DD/MM/AA' con la fecha de follow
        5. Ninguno → 'Visita'
        """
        user_id = chatter.id

        if chatter.id == broadcaster_id:
            return "Broadcaster"

        if user_id == self.bot.bot_id:
            return "Bot"

        if await is_user_bot(self.bot.app_database, user_id):
            return "Bot"

        follow = await chatter.follow_info()
        if follow and follow.followed_at:
            return follow.followed_at.strftime("%d/%m/%y")

        return "Visita"

    @commands.Component.listener()
    async def event_message(self, payload: twitchio.ChatMessage) -> None:
        """Guarda el mensaje en el historial y emite un ChatMessageEvent."""
        chatter = payload.chatter
        user_id = chatter.id
        username = chatter.name or user_id
        display_name = chatter.display_name or username

        await upsert_user(
            self.bot.app_database,
            user_id,
            username,
            display_name,
            is_moderator=chatter.moderator,
            is_vip=chatter.vip,
            is_subscriber=chatter.subscriber,
        )

        es_bot = await is_user_bot(self.bot.app_database, user_id)
        if not es_bot:
            await save_chat_message(
                self.bot.app_database,
                payload.broadcaster.id,
                user_id,
                payload.text,
            )

        nickname = await get_user_nickname(self.bot.app_database, user_id)

        hex_str = chatter.color.hex if chatter.color else None
        r, g, b = get_chatter_rgb(hex_str, username)

        role = await self._get_chatter_role(chatter, payload.broadcaster.id)

        await self.bot.event_bus.emit(
            ChatMessageEvent(
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
            )
        )

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
