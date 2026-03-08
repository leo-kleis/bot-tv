from __future__ import annotations

import logging

import asqlite
import twitchio
from twitchio import eventsub
from twitchio.ext import commands

from bot_tv.env import (
    BOT_ID,
    CLIENT_ID,
    CLIENT_SECRET,
    OWNER_ID,
)

LOGGER = logging.getLogger(__name__)


class Bot(commands.AutoBot):
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
        # Importación tardía para evitar dependencias circulares:
        # Los componentes necesitan conocer el tipo Bot, y Bot necesita
        # instanciarlos. Al importar aquí, ambos módulos ya están cargados.
        from bot_tv.components.followers_component import FollowersComponent
        from bot_tv.components.mi_componente import MiComponente

        await self.add_component(MiComponente(self))
        await self.add_component(FollowersComponent(self))

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

    async def add_token(
        self, token: str, refresh: str
    ) -> twitchio.authentication.ValidateTokenPayload:
        """Añade y persiste un token de acceso en la base de datos."""
        from bot_tv.database import save_token

        resp: twitchio.authentication.ValidateTokenPayload = await super().add_token(
            token, refresh
        )
        if resp.user_id and resp.login:
            await save_token(
                self.token_database, resp.user_id, resp.login, token, refresh
            )
            LOGGER.info("Token almacenado para: %s (ID: %s)", resp.login, resp.user_id)
        return resp

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

        # Disparar un evento personalizado indicando que el bot ya imprimió su conexión,
        # para que componentes pesados (como followers) puedan iniciar tranquilos.
        self.dispatch("bot_fully_connected")

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
