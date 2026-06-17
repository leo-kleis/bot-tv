from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from bot_tv.events import (
    StreamOfflineEvent,
    StreamOnlineEvent,
    ViewerUpdateEvent,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)

VIEWER_POLL_INTERVAL = 60


class StreamComponent(commands.Component):
    """Componente que monitorea el estado del stream y muestra viewers.

    Funcionalidad:
    - Detecta stream online/offline via EventSub (instantáneo)
    - Emite ViewerUpdateEvent con el viewer count cuando cambia (polling cada 60s)
    """

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._viewer_task: asyncio.Task[None] | None = None
        self._last_viewer_count: int | None = None
        self._stream_online: bool = False
        self._channel_ids: list[str] = []

    # ── Ciclo de vida ───────────────────────────────────────────────

    @commands.Component.listener()
    async def event_bot_fully_connected(self) -> None:
        """Inicia el monitoreo cuando el bot está completamente conectado."""
        channels = await self.bot.get_channels()
        self._channel_ids = [channel["user_id"] for channel in channels]

        if not self._channel_ids:
            LOGGER.warning("StreamComponent: no hay canales para monitorear.")
            return

        await self._check_initial_status()
        self._viewer_task = asyncio.create_task(self._viewer_poll_loop())

    async def component_teardown(self) -> None:
        """Detiene el polling al cerrar el componente."""
        if self._viewer_task and not self._viewer_task.done():
            self._viewer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._viewer_task

    # ── EventSub: Stream Online/Offline ─────────────────────────────

    @commands.Component.listener()
    async def event_eventsub_notification_stream_start(
        self, payload: twitchio.StreamOnline
    ) -> None:
        """Se ejecuta cuando un stream se pone online (EventSub)."""
        self._stream_online = True
        self._last_viewer_count = None

        titulo = ""
        categoria = ""
        with contextlib.suppress(Exception):
            streams = self.bot.fetch_streams(user_ids=[int(payload.broadcaster.id)])
            async for stream in streams:
                titulo = stream.title or ""
                categoria = stream.game_name or ""
                break

        nombre = payload.broadcaster.display_name or payload.broadcaster.name or ""

        await self.bot.event_bus.emit(
            StreamOnlineEvent(
                timestamp=datetime.now().isoformat(),
                broadcaster_name=nombre,
                title=titulo,
                category=categoria,
            )
        )

    @commands.Component.listener()
    async def event_eventsub_notification_stream_end(
        self, payload: twitchio.StreamOffline
    ) -> None:
        """Se ejecuta cuando un stream se pone offline (EventSub)."""
        self._stream_online = False
        self._last_viewer_count = None

        nombre = payload.broadcaster.display_name or payload.broadcaster.name or ""

        await self.bot.event_bus.emit(
            StreamOfflineEvent(
                timestamp=datetime.now().isoformat(),
                broadcaster_name=nombre,
            )
        )

    # ── Polling de viewers ──────────────────────────────────────────

    async def _check_initial_status(self) -> None:
        """Verifica el estado del stream al iniciar el componente."""
        for channel_id in self._channel_ids:
            try:
                streams = self.bot.fetch_streams(user_ids=[int(channel_id)])
                async for stream in streams:
                    self._stream_online = True
                    viewer_count = stream.viewer_count
                    self._last_viewer_count = viewer_count

                    nombre = stream.user.display_name or stream.user.name or ""
                    titulo = stream.title or ""
                    categoria = stream.game_name or ""

                    await self.bot.event_bus.emit(
                        StreamOnlineEvent(
                            timestamp=datetime.now().isoformat(),
                            broadcaster_name=nombre,
                            title=titulo,
                            category=categoria,
                        )
                    )
                    await self.bot.event_bus.emit(
                        ViewerUpdateEvent(
                            timestamp=datetime.now().isoformat(),
                            count=viewer_count,
                            diff=None,
                        )
                    )
                    break
                else:
                    await self.bot.event_bus.emit(
                        StreamOfflineEvent(
                            timestamp=datetime.now().isoformat(),
                            broadcaster_name="",
                        )
                    )
            except Exception as e:
                LOGGER.error("Error al verificar estado inicial del stream: %s", e)

    async def _viewer_poll_loop(self) -> None:
        """Loop que consulta el estado del stream y viewers periódicamente."""
        while True:
            await asyncio.sleep(VIEWER_POLL_INTERVAL)

            for channel_id in self._channel_ids:
                try:
                    streams = self.bot.fetch_streams(user_ids=[int(channel_id)])
                    stream_obj = None
                    async for stream in streams:
                        stream_obj = stream
                        break

                    if stream_obj:
                        viewer_count = stream_obj.viewer_count
                        # Si antes estaba offline
                        if not self._stream_online:
                            self._stream_online = True
                            self._last_viewer_count = viewer_count
                            nombre = (
                                stream_obj.user.display_name
                                or stream_obj.user.name
                                or ""
                            )
                            titulo = stream_obj.title or ""
                            categoria = stream_obj.game_name or ""
                            await self.bot.event_bus.emit(
                                StreamOnlineEvent(
                                    timestamp=datetime.now().isoformat(),
                                    broadcaster_name=nombre,
                                    title=titulo,
                                    category=categoria,
                                )
                            )
                            await self.bot.event_bus.emit(
                                ViewerUpdateEvent(
                                    timestamp=datetime.now().isoformat(),
                                    count=viewer_count,
                                    diff=None,
                                )
                            )
                        elif viewer_count != self._last_viewer_count:
                            diff = (
                                viewer_count - self._last_viewer_count
                                if self._last_viewer_count is not None
                                else None
                            )
                            self._last_viewer_count = viewer_count
                            await self.bot.event_bus.emit(
                                ViewerUpdateEvent(
                                    timestamp=datetime.now().isoformat(),
                                    count=viewer_count,
                                    diff=diff,
                                )
                            )
                    else:
                        # Si antes estaba online pero ahora ya no se encuentra el stream
                        if self._stream_online:
                            self._stream_online = False
                            self._last_viewer_count = None
                            await self.bot.event_bus.emit(
                                StreamOfflineEvent(
                                    timestamp=datetime.now().isoformat(),
                                    broadcaster_name="",
                                )
                            )
                except Exception as e:
                    LOGGER.error("Error al consultar estado/viewers del stream: %s", e)
