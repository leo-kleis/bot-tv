from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import asyncpg
import twitchio
from twitchio import eventsub
from twitchio.authentication import ManagedHTTPClient
from twitchio.ext import commands

from bot_tv.components.chat_component import ChatComponent
from bot_tv.components.clip_component import ClipComponent
from bot_tv.components.followers_component import FollowersComponent
from bot_tv.components.stream_component import StreamComponent
from bot_tv.components.twitch_events_component import TwitchEventsComponent
from bot_tv.database import (
    AnalyticsRepository,
    ChannelUserRepository,
    ChatRepository,
    SettingsRepository,
    TokenPersistMixin,
    TokenRepository,
    UserMemoryCache,
    UserRepository,
)
from bot_tv.event_bus import EventBus
from bot_tv.irc import TwitchIRCClient
from bot_tv.utils.env import (
    BOT_ID,
    CLIENT_ID,
    CLIENT_SECRET,
    IRC_TOKEN,
    OWNER_ID,
)

if TYPE_CHECKING:
    from bot_tv.agent.client import TalkAgent

LOGGER = logging.getLogger(__name__)


class Bot(TokenPersistMixin, commands.AutoBot):
    """Bot principal de Twitch TV."""

    def __init__(
        self,
        *,
        database: asyncpg.Pool,
        subs: list[eventsub.SubscriptionPayload],
        event_bus: EventBus,
    ) -> None:
        self.database = database
        self.event_bus = event_bus
        self._irc_task: asyncio.Task[None] | None = None
        self._preload_task: asyncio.Task[None] | None = None
        self._cache_ready: bool = False
        self.irc: TwitchIRCClient | None = None
        self.agent: TalkAgent | None = None

        self.current_stream_id: str | None = None
        self._channels_cache: list[dict[str, str]] | None = None

        # Instanciar repositorios y caché de memoria
        self.user_cache = UserMemoryCache()
        self.token_repo = TokenRepository(database)
        self.user_repo = UserRepository(database)
        self.chat_repo = ChatRepository(database)
        self.channel_user_repo = ChannelUserRepository(database)
        self.settings_repo = SettingsRepository(database)
        self.analytics_repo = AnalyticsRepository(database)

        super().__init__(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            bot_id=BOT_ID,
            owner_id=OWNER_ID,
            prefix="?",
            subscriptions=subs,
            force_subscribe=True,
        )

    @property
    def twitch_http(self) -> ManagedHTTPClient:
        """Retorna el cliente HTTP gestionado de TwitchIO."""
        return self._http

    def get_component(self, name: str) -> commands.Component | None:
        """Retorna un componente registrado por nombre."""
        return super().get_component(name)

    @property
    def ready_user_cache(self) -> UserMemoryCache | None:
        """Retorna la caché en memoria solo tras completar la precarga inicial."""
        return self.user_cache if self._cache_ready else None

    async def _preload_user_cache(self) -> None:
        """Precarga usuarios y roles en memoria sin bloquear el arranque."""
        try:
            await self.user_repo.preload_cache(self.user_cache)
            self._cache_ready = True
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception(
                "Error al precargar caché de usuarios; "
                "se continuará operando contra PostgreSQL."
            )

    async def setup_hook(self) -> None:
        """Registra los componentes del bot."""
        await self.add_component(ChatComponent(self))
        await self.add_component(FollowersComponent(self))
        await self.add_component(ClipComponent(self))
        await self.add_component(StreamComponent(self))
        await self.add_component(TwitchEventsComponent(self))

    async def event_oauth_authorized(
        self, payload: twitchio.authentication.UserTokenPayload
    ) -> None:
        """Se ejecuta cuando un usuario autoriza la aplicación."""
        await self.add_token(payload.access_token, payload.refresh_token)

        if not payload.user_id or payload.user_id == self.bot_id:
            return

        subs = TokenRepository.get_user_subscriptions(payload.user_id, self.bot_id)
        resp: twitchio.MultiSubscribePayload = await self.multi_subscribe(subs)
        if resp.errors:
            LOGGER.warning(
                "Error al suscribirse a: %r, para el usuario: %s",
                resp.errors,
                payload.user_id,
            )

    async def get_channels(self) -> list[dict[str, str]]:
        """Retorna la lista de canales configurados (excluyendo al bot)."""
        if self._channels_cache is not None:
            return self._channels_cache
        accounts = await self.token_repo.get_accounts_summary()
        self._channels_cache = [
            {"user_id": row["user_id"], "username": row["username"]}
            for row in accounts
            if row["user_id"] != self.bot_id
        ]
        return self._channels_cache

    async def event_websocket_welcome(self, payload: Any) -> None:
        """Se ejecuta cuando el websocket de EventSub se conecta con éxito."""
        LOGGER.info("Conexión con EventSub (Chat/Eventos) establecida con éxito.")

    async def event_ready(self) -> None:
        """Se ejecuta cuando el bot se conecta correctamente."""
        if not self._cache_ready and (
            self._preload_task is None or self._preload_task.done()
        ):
            self._preload_task = asyncio.create_task(self._preload_user_cache())
        accounts = await self.token_repo.get_accounts_summary()
        self._channels_cache = [
            {"user_id": row["user_id"], "username": row["username"]}
            for row in accounts
            if row["user_id"] != self.bot_id
        ]

        bot_name = self.bot_id
        canales: list[str] = [c["username"] for c in self._channels_cache]
        for row in accounts:
            if row["user_id"] == self.bot_id:
                bot_name = row["username"]
                break

        LOGGER.info("Bot conectado como: %s (ID: %s)", bot_name, self.bot_id)
        if canales:
            LOGGER.info("Escuchando en canales: %s", ", ".join(canales))
        else:
            LOGGER.warning("No hay canales configurados.")

        # Iniciar el cliente IRC
        if not IRC_TOKEN:
            LOGGER.warning(
                "No se encontró el token de IRC (IRC_TOKEN) en el archivo .env. "
                "El bot iniciará sin IRC."
            )
        elif canales:
            self.irc = TwitchIRCClient(
                bot=self,
                database=self.database,
                bot_username=bot_name,
                token=IRC_TOKEN,
                canales=canales,
            )
            self._irc_task = asyncio.create_task(self.irc.connect())
            try:
                await asyncio.wait_for(self.irc.connected_event.wait(), timeout=15.0)
            except Exception:
                LOGGER.warning("Continuando arranque sin esperar más al IRC.")

        self.dispatch("bot_fully_connected")

    async def close(self, **options: Any) -> None:
        """Cancela tareas pendientes antes de cerrar el bot."""
        if self.current_stream_id is not None:
            stream_id = self.current_stream_id
            self.current_stream_id = None
            try:
                await self.analytics_repo.close_session(
                    stream_id,
                    datetime.now(UTC),
                    "graceful_shutdown",
                )
            except Exception as e:
                LOGGER.warning("Error al cerrar sesión en shutdown: %s", e)

        if self._preload_task and not self._preload_task.done():
            self._preload_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._preload_task

        if self.agent is not None:
            await self.agent.close()

        await self.chat_repo.close()

        if self._irc_task and not self._irc_task.done():
            if self.irc:
                self.irc._running = False
            self._irc_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._irc_task
        if self.irc is not None:
            await self.irc.close()

        await super().close(**options)

    async def event_command_error(self, payload: commands.CommandErrorPayload) -> None:
        """Maneja los errores globalmente (evitando el log doble de TwitchIO)."""
        error = payload.exception

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            return

        ctx = payload.context
        nombre_comando = ctx.command.name if ctx.command else "?"
        LOGGER.exception(
            "[BOT] Error global no manejado en '?%s'", nombre_comando, exc_info=error
        )
