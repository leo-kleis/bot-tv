from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands
from twitchio.http import Route

from bot_tv.events import (
    StreamOfflineEvent,
    StreamOnlineEvent,
    StreamUpdateEvent,
    ViewerUpdateEvent,
)
from bot_tv.utils.formatting import parse_twitch_duration

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
        self._channel_map: dict[str, str] = {}
        self._offline_counts: dict[str, int] = {}

    async def _reconcile_orphan_sessions(self) -> None:
        """Reconcilia sesiones huérfanas al iniciar el bot."""
        try:
            orphans = await self.bot.analytics_repo.get_orphan_sessions()
        except Exception:
            LOGGER.exception("Error al consultar sesiones huérfanas.")
            return

        for orphan in orphans:
            orphan_stream_id = str(orphan["stream_id"])
            channel_id = str(orphan["channel_id"])
            try:
                # Consultar si sigue en vivo
                is_still_live = False
                streams_iter = self.bot.fetch_streams(user_ids=[int(channel_id)])
                async for stream in streams_iter:
                    if stream.id == orphan_stream_id:
                        is_still_live = True
                        self.bot.current_stream_id = orphan_stream_id
                        self._stream_online = True
                    break

                if is_still_live:
                    continue

                # Si ya terminó, intentar obtener el VOD correspondiente
                vod_found = False
                route = Route(
                    "GET",
                    "videos",
                    params={"user_id": channel_id, "type": "archive", "first": 20},
                )
                try:
                    resp = await self.bot.http.request(route)
                    if isinstance(resp, dict):
                        videos = resp.get("data", [])
                        for vod in videos:
                            if str(vod.get("stream_id")) == orphan_stream_id:
                                started_at = orphan["started_at"]
                                if isinstance(started_at, str):
                                    started_at = datetime.fromisoformat(started_at)
                                if started_at.tzinfo is None:
                                    started_at = started_at.replace(tzinfo=UTC)

                                duration_secs = parse_twitch_duration(
                                    vod.get("duration", "")
                                )
                                ended_at = started_at + timedelta(seconds=duration_secs)
                                await self.bot.analytics_repo.close_session(
                                    orphan_stream_id, ended_at, "orphan_recovery_vod"
                                )
                                vod_found = True
                                break
                except Exception:
                    LOGGER.debug(
                        "Error al consultar VOD para la sesión huérfana %s",
                        orphan_stream_id,
                    )

                if not vod_found:
                    await self.bot.analytics_repo.close_orphan_session_fast(
                        orphan_stream_id
                    )
            except Exception:
                LOGGER.exception(
                    "Error al reconciliar sesión huérfana %s", orphan_stream_id
                )

    # ── Ciclo de vida ───────────────────────────────────────────────

    @commands.Component.listener()
    async def event_bot_fully_connected(self) -> None:
        """Inicia el monitoreo cuando el bot está completamente conectado."""
        channels = await self.bot.get_channels()
        self._channel_ids = [channel["user_id"] for channel in channels]
        self._channel_map = {}

        missing_ids: list[int | str] = []
        for c in channels:
            cid = c["user_id"]
            name = c["username"]
            cached = self.bot.user_cache.get_user(cid)
            if cached and cached.get("display_name"):
                name = cached["display_name"]
            else:
                with contextlib.suppress(ValueError):
                    missing_ids.append(int(cid))
            self._channel_map[cid] = name

        if missing_ids:
            with contextlib.suppress(Exception):
                users = await self.bot.fetch_users(ids=missing_ids)
                for u in users:
                    if u.id and u.display_name:
                        self._channel_map[u.id] = u.display_name

        if not self._channel_ids:
            LOGGER.warning("StreamComponent: no hay canales para monitorear.")
            return

        await self._reconcile_orphan_sessions()
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
    async def event_stream_online(self, payload: twitchio.StreamOnline) -> None:
        """Se ejecuta cuando un stream se pone online (EventSub)."""
        self._stream_online = True
        self._last_viewer_count = None
        self.bot.current_stream_id = payload.id
        channel_id = payload.broadcaster.id
        self._offline_counts[channel_id] = 0

        titulo = ""
        categoria = ""
        with contextlib.suppress(Exception):
            streams = self.bot.fetch_streams(user_ids=[int(payload.broadcaster.id)])
            async for stream in streams:
                titulo = stream.title or ""
                categoria = stream.game_name or ""
                break

        nombre = payload.broadcaster.display_name or payload.broadcaster.name or ""

        started_at = (
            payload.started_at
            if hasattr(payload, "started_at") and payload.started_at
            else datetime.now(UTC)
        )

        with contextlib.suppress(Exception):
            await self.bot.analytics_repo.create_or_get_session(
                channel_id=channel_id,
                stream_id=payload.id,
                started_at=started_at,
                title=titulo,
                category_name=categoria,
            )

        if hasattr(payload, "started_at") and payload.started_at:
            if hasattr(payload.started_at, "isoformat"):
                started_at_str = payload.started_at.isoformat()
            else:
                started_at_str = str(payload.started_at)
        else:
            started_at_str = datetime.now(UTC).isoformat()

        await self.bot.event_bus.emit(
            StreamOnlineEvent(
                timestamp=datetime.now().isoformat(),
                broadcaster_name=nombre,
                title=titulo,
                category=categoria,
                started_at=started_at_str,
            )
        )

    @commands.Component.listener()
    async def event_stream_offline(self, payload: twitchio.StreamOffline) -> None:
        """Se ejecuta cuando un stream se pone offline (EventSub)."""
        self._stream_online = False
        self._last_viewer_count = None
        channel_id = payload.broadcaster.id
        self._offline_counts[channel_id] = 0

        target_stream_id = self.bot.current_stream_id or getattr(payload, "id", None)
        if target_stream_id:
            with contextlib.suppress(Exception):
                await self.bot.analytics_repo.close_session(
                    target_stream_id,
                    datetime.now(UTC),
                    "eventsub_offline",
                )
        self.bot.current_stream_id = None

        nombre = (
            payload.broadcaster.display_name
            or payload.broadcaster.name
            or self._channel_map.get(channel_id, "")
        )
        titulo = ""
        categoria = ""
        with contextlib.suppress(Exception):
            info = await self.bot.fetch_channel(broadcaster_id=int(channel_id))
            if info:
                titulo = info.title or ""
                categoria = info.game_name or ""

        await self.bot.event_bus.emit(
            StreamOfflineEvent(
                timestamp=datetime.now().isoformat(),
                broadcaster_name=nombre,
                title=titulo,
                category=categoria,
            )
        )

    @commands.Component.listener()
    async def event_channel_update(self, payload: twitchio.ChannelUpdate) -> None:
        """Se ejecuta cuando un stream actualiza título o categoría (EventSub)."""
        nombre = payload.broadcaster.display_name or payload.broadcaster.name or ""
        titulo = payload.title or ""
        categoria = (
            getattr(payload, "category_name", None)
            or getattr(payload, "game_name", None)
            or ""
        )

        await self.bot.event_bus.emit(
            StreamUpdateEvent(
                timestamp=datetime.now().isoformat(),
                broadcaster_name=nombre,
                title=titulo,
                category=categoria,
            )
        )

    # ── Polling de viewers ──────────────────────────────────────────

    async def _check_initial_status(self) -> None:
        """Verifica el estado del stream al iniciar el componente."""
        if not self._channel_ids:
            return

        chunk_size = 100
        for i in range(0, len(self._channel_ids), chunk_size):
            chunk_ids = self._channel_ids[i : i + chunk_size]
            try:
                streams_iter = self.bot.fetch_streams(
                    user_ids=[int(cid) for cid in chunk_ids]
                )
                live_streams = {}
                async for stream in streams_iter:
                    live_streams[stream.user.id] = stream

                for channel_id in chunk_ids:
                    stream = live_streams.get(channel_id)
                    if stream:
                        self._stream_online = True
                        viewer_count = stream.viewer_count
                        self._last_viewer_count = viewer_count
                        self._offline_counts[channel_id] = 0
                        self.bot.current_stream_id = stream.id

                        nombre = stream.user.display_name or stream.user.name or ""
                        titulo = stream.title or ""
                        categoria = stream.game_name or ""
                        started_at = stream.started_at

                        with contextlib.suppress(Exception):
                            await self.bot.analytics_repo.create_or_get_session(
                                channel_id=channel_id,
                                stream_id=stream.id,
                                started_at=started_at,
                                title=titulo,
                                category_name=categoria,
                            )
                            await self.bot.analytics_repo.save_viewer_snapshot(
                                channel_id, stream.id, viewer_count
                            )
                            await self.bot.analytics_repo.update_session_viewers(
                                stream.id, viewer_count
                            )

                        started_at_str = (
                            stream.started_at.isoformat()
                            if hasattr(stream.started_at, "isoformat")
                            else str(stream.started_at)
                        )

                        await self.bot.event_bus.emit(
                            StreamOnlineEvent(
                                timestamp=datetime.now().isoformat(),
                                broadcaster_name=nombre,
                                title=titulo,
                                category=categoria,
                                started_at=started_at_str,
                            )
                        )
                        await self.bot.event_bus.emit(
                            ViewerUpdateEvent(
                                timestamp=datetime.now().isoformat(),
                                count=viewer_count,
                                diff=None,
                            )
                        )
                    else:
                        self._offline_counts[channel_id] = 0
                        nombre = self._channel_map.get(channel_id, "")
                        titulo = ""
                        categoria = ""
                        with contextlib.suppress(Exception):
                            info = await self.bot.fetch_channel(
                                broadcaster_id=int(channel_id)
                            )
                            if info:
                                titulo = info.title or ""
                                categoria = info.game_name or ""
                                if info.user and (
                                    info.user.display_name or info.user.name
                                ):
                                    nombre = (
                                        info.user.display_name
                                        or info.user.name
                                        or nombre
                                    )

                        await self.bot.event_bus.emit(
                            StreamOfflineEvent(
                                timestamp=datetime.now().isoformat(),
                                broadcaster_name=nombre,
                                title=titulo,
                                category=categoria,
                            )
                        )
            except Exception as e:
                LOGGER.error("Error al verificar estado inicial del stream: %s", e)

    async def _viewer_poll_loop(self) -> None:
        """Loop que consulta el estado del stream y viewers periódicamente."""
        while True:
            await asyncio.sleep(VIEWER_POLL_INTERVAL)

            if not self._channel_ids:
                continue

            chunk_size = 100
            for i in range(0, len(self._channel_ids), chunk_size):
                chunk_ids = self._channel_ids[i : i + chunk_size]
                try:
                    streams_iter = self.bot.fetch_streams(
                        user_ids=[int(cid) for cid in chunk_ids]
                    )
                    live_streams = {}
                    async for stream in streams_iter:
                        live_streams[stream.user.id] = stream

                    for channel_id in chunk_ids:
                        stream_obj = live_streams.get(channel_id)

                        if stream_obj:
                            viewer_count = stream_obj.viewer_count
                            self._offline_counts[channel_id] = 0

                            # Reconexión o stream online no detectado por EventSub
                            if (
                                not self._stream_online
                                or self.bot.current_stream_id != stream_obj.id
                            ):
                                self._stream_online = True
                                self._last_viewer_count = viewer_count
                                self.bot.current_stream_id = stream_obj.id

                                nombre = (
                                    stream_obj.user.display_name
                                    or stream_obj.user.name
                                    or ""
                                )
                                titulo = stream_obj.title or ""
                                categoria = stream_obj.game_name or ""
                                started_at = stream_obj.started_at

                                with contextlib.suppress(Exception):
                                    await self.bot.analytics_repo.create_or_get_session(
                                        channel_id=channel_id,
                                        stream_id=stream_obj.id,
                                        started_at=started_at,
                                        title=titulo,
                                        category_name=categoria,
                                    )

                                started_at_str = (
                                    stream_obj.started_at.isoformat()
                                    if hasattr(stream_obj.started_at, "isoformat")
                                    else str(stream_obj.started_at)
                                )
                                await self.bot.event_bus.emit(
                                    StreamOnlineEvent(
                                        timestamp=datetime.now().isoformat(),
                                        broadcaster_name=nombre,
                                        title=titulo,
                                        category=categoria,
                                        started_at=started_at_str,
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

                            # En cada tick con stream online:
                            with contextlib.suppress(Exception):
                                await self.bot.analytics_repo.save_viewer_snapshot(
                                    channel_id, stream_obj.id, viewer_count
                                )
                                await self.bot.analytics_repo.update_session_viewers(
                                    stream_obj.id, viewer_count
                                )
                        else:
                            # Anti-flapping: umbral de 2 ciclos consecutivos (120s)
                            if self._stream_online:
                                self._offline_counts[channel_id] = (
                                    self._offline_counts.get(channel_id, 0) + 1
                                )
                                if self._offline_counts[channel_id] >= 2:
                                    self._stream_online = False
                                    self._last_viewer_count = None
                                    self._offline_counts[channel_id] = 0

                                    target_stream_id = self.bot.current_stream_id
                                    if target_stream_id:
                                        with contextlib.suppress(Exception):
                                            await self.bot.analytics_repo.close_session(
                                                target_stream_id,
                                                datetime.now(UTC),
                                                "poll_offline_timeout",
                                            )
                                        self.bot.current_stream_id = None

                                    nombre = self._channel_map.get(channel_id, "")
                                    titulo = ""
                                    categoria = ""
                                    with contextlib.suppress(Exception):
                                        info = await self.bot.fetch_channel(
                                            broadcaster_id=int(channel_id)
                                        )
                                        if info:
                                            titulo = info.title or ""
                                            categoria = info.game_name or ""

                                    await self.bot.event_bus.emit(
                                        StreamOfflineEvent(
                                            timestamp=datetime.now().isoformat(),
                                            broadcaster_name=nombre,
                                            title=titulo,
                                            category=categoria,
                                        )
                                    )
                except Exception as e:
                    LOGGER.error("Error al consultar estado/viewers del stream: %s", e)
