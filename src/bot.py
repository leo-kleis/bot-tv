from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import asqlite
import twitchio
from twitchio import eventsub
from twitchio.ext import commands

from components.chat_component import ChatComponent
from components.clip_component import ClipComponent
from components.followers_component import FollowersComponent
from components.stream_component import StreamComponent
from database.tokens import TokenPersistMixin
from irc import TwitchIRCClient
from utils.env import (
    BOT_ID,
    CLIENT_ID,
    CLIENT_SECRET,
    IRC_TOKEN,
    OWNER_ID,
)

LOGGER = logging.getLogger(__name__)


class Bot(TokenPersistMixin, commands.AutoBot):
    """Bot principal de Twitch TV."""

    def __init__(
        self,
        *,
        token_database: asqlite.Pool,
        app_database: asqlite.Pool,
        subs: list[eventsub.SubscriptionPayload],
    ) -> None:
        self.token_database = token_database
        self.app_database = app_database
        self._irc_task: asyncio.Task[None] | None = None

        super().__init__(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            bot_id=BOT_ID,
            owner_id=OWNER_ID,
            prefix="?",
            subscriptions=subs,
            force_subscribe=True,
        )

    async def setup_hook(self) -> None:
        """Registra los componentes del bot."""
        await self.add_component(ChatComponent(self))
        await self.add_component(FollowersComponent(self))
        await self.add_component(ClipComponent(self))
        await self.add_component(StreamComponent(self))

    async def event_oauth_authorized(
        self, payload: twitchio.authentication.UserTokenPayload
    ) -> None:
        """Se ejecuta cuando un usuario autoriza la aplicación."""
        await self.add_token(payload.access_token, payload.refresh_token)

        if not payload.user_id or payload.user_id == self.bot_id:
            return

        subs: list[eventsub.SubscriptionPayload] = [
            eventsub.ChatMessageSubscription(
                broadcaster_user_id=payload.user_id, user_id=self.bot_id
            ),
        ]
        resp: twitchio.MultiSubscribePayload = await self.multi_subscribe(subs)
        if resp.errors:
            LOGGER.warning(
                "Error al suscribirse a: %r, para el usuario: %s",
                resp.errors,
                payload.user_id,
            )

    async def get_channels(self) -> list[dict[str, str]]:
        """Retorna la lista de canales configurados (excluyendo al bot)."""
        async with self.token_database.acquire() as conn:
            rows = await conn.fetchall("SELECT user_id, username FROM tokens")
        return [
            {"user_id": row["user_id"], "username": row["username"]}
            for row in rows
            if row["user_id"] != self.bot_id
        ]

    async def event_ready(self) -> None:
        """Se ejecuta cuando el bot se conecta correctamente."""
        async with self.token_database.acquire() as connection:
            rows = await connection.fetchall("SELECT user_id, username FROM tokens")

        bot_name = self.bot_id
        canales: list[str] = []
        for row in rows:
            if row["user_id"] == self.bot_id:
                bot_name = row["username"]
            else:
                canales.append(row["username"])

        LOGGER.info("Bot conectado como: %s (ID: %s)", bot_name, self.bot_id)
        if canales:
            LOGGER.info("Escuchando en canales: %s", ", ".join(canales))
        else:
            LOGGER.warning("No hay canales configurados.")

        # Iniciar el cliente IRC
        if canales and IRC_TOKEN:
            irc = TwitchIRCClient(
                bot=self,
                app_database=self.app_database,
                bot_username=bot_name,
                token=IRC_TOKEN,
                canales=canales,
            )
            self._irc_task = asyncio.create_task(irc.connect())
        else:
            LOGGER.warning("IRC no iniciado: falta IRC_TOKEN o no hay canales.")

        # Disparar un evento personalizado indicando que el bot ya imprimió su conexión,
        # para que componentes pesados (como followers) puedan iniciar tranquilos.
        self.dispatch("bot_fully_connected")

    async def close(self, **options: Any) -> None:
        """Cancela tareas pendientes antes de cerrar el bot."""
        if self._irc_task and not self._irc_task.done():
            self._irc_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._irc_task
        await super().close(**options)

    async def event_command_error(self, payload: commands.CommandErrorPayload) -> None:
        """Maneja los errores globalmente (evitando el log doble de TwitchIO)."""
        error = payload.exception

        # Ignorar cuando el comando no existe (ej: ?comoestas)
        if isinstance(error, commands.CommandNotFound):
            return

        # Ignorar errores de argumentos
        # (ya estamos manejándolos en nuestros componentes)
        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            return

        # Cualquier otro error no deseado lo logeamos limpiamente nosotros mismos
        ctx = payload.context
        nombre_comando = ctx.command.name if ctx.command else "?"
        LOGGER.exception(
            "[BOT] Error global no manejado en '?%s'", nombre_comando, exc_info=error
        )
