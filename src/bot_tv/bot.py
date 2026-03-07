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
        subs: list[eventsub.SubscriptionPayload],
    ) -> None:
        self.token_database = token_database

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
        # MiComponente necesita conocer el tipo Bot, y Bot necesita instanciar
        # MiComponente. Al importar aquí, ambos módulos ya están cargados.
        from bot_tv.components.mi_componente import MiComponente

        await self.add_component(MiComponente(self))

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
        if resp.user_id:
            await save_token(self.token_database, resp.user_id, token, refresh)
            LOGGER.info("Token almacenado para el usuario: %s", resp.user_id)
        return resp

    async def event_ready(self) -> None:
        """Se ejecuta cuando el bot se conecta correctamente."""
        LOGGER.info("Bot conectado como: %s", self.bot_id)
