"""WebSocket handler: consume el EventBus y transmite eventos a clientes web."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from bot_tv.events import (
    AgentResponseEvent,
    BotLogEvent,
    ChatMessageEvent,
    ClipCreatedEvent,
    FollowerProgressEvent,
    FollowerSyncEvent,
    StreamOfflineEvent,
    StreamOnlineEvent,
    StreamUpdateEvent,
    TwitchBanEvent,
    TwitchChannelPointsRedeemEvent,
    TwitchChatClearEvent,
    TwitchChatClearUserEvent,
    TwitchCheerEvent,
    TwitchFollowEvent,
    TwitchIRCStatusEvent,
    TwitchMessageDeleteEvent,
    TwitchPredictionBeginEvent,
    TwitchPredictionEndEvent,
    TwitchPredictionLockEvent,
    TwitchPredictionProgressEvent,
    TwitchRaidEvent,
    TwitchSubscribeEvent,
    TwitchSubscriptionGiftEvent,
    TwitchSubscriptionMessageEvent,
    TwitchUnbanEvent,
    UserJoinEvent,
    UserNicknameUpdatedEvent,
    UserPartEvent,
    UserRoleUpdatedEvent,
    ViewerUpdateEvent,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot
    from bot_tv.event_bus import EventBus

LOGGER = logging.getLogger(__name__)

MAX_WS_CLIENTS = 20
WS_SEND_TIMEOUT_SECONDS = 2.0
WS_POLICY_VIOLATION_CODE = 1008

# Mapeo tipo de evento Python → tipo de mensaje JSON
EVENT_TYPE_MAP: dict[type, str] = {
    ChatMessageEvent: "chat_message",
    UserJoinEvent: "user_join",
    UserPartEvent: "user_part",
    UserRoleUpdatedEvent: "user_role_updated",
    UserNicknameUpdatedEvent: "user_nickname_updated",
    StreamOnlineEvent: "stream_online",
    StreamOfflineEvent: "stream_offline",
    StreamUpdateEvent: "stream_update",
    ViewerUpdateEvent: "viewer_update",
    FollowerSyncEvent: "follower_sync",
    FollowerProgressEvent: "follower_progress",
    AgentResponseEvent: "agent_response",
    ClipCreatedEvent: "clip_created",
    BotLogEvent: "bot_log",
    TwitchFollowEvent: "twitch_follow",
    TwitchRaidEvent: "twitch_raid",
    TwitchSubscribeEvent: "twitch_subscribe",
    TwitchSubscriptionGiftEvent: "twitch_sub_gift",
    TwitchSubscriptionMessageEvent: "twitch_sub_message",
    TwitchCheerEvent: "twitch_cheer",
    TwitchChannelPointsRedeemEvent: "twitch_points_redeem",
    TwitchPredictionBeginEvent: "prediction_begin",
    TwitchPredictionProgressEvent: "prediction_progress",
    TwitchPredictionLockEvent: "prediction_lock",
    TwitchPredictionEndEvent: "prediction_end",
    TwitchBanEvent: "twitch_ban",
    TwitchUnbanEvent: "twitch_unban",
    TwitchChatClearEvent: "twitch_chat_clear",
    TwitchChatClearUserEvent: "twitch_chat_clear_user",
    TwitchMessageDeleteEvent: "twitch_message_delete",
    TwitchIRCStatusEvent: "irc_status",
}

# Tipos de eventos que se incluyen en el historial inicial al conectar
HISTORY_EVENT_TYPES: list[type] = [
    ChatMessageEvent,
    UserRoleUpdatedEvent,
    UserNicknameUpdatedEvent,
    StreamOnlineEvent,
    StreamOfflineEvent,
    ViewerUpdateEvent,
    FollowerSyncEvent,
    FollowerProgressEvent,
    AgentResponseEvent,
    ClipCreatedEvent,
    TwitchFollowEvent,
    TwitchRaidEvent,
    TwitchSubscribeEvent,
    TwitchSubscriptionGiftEvent,
    TwitchSubscriptionMessageEvent,
    TwitchCheerEvent,
    TwitchChannelPointsRedeemEvent,
    TwitchPredictionBeginEvent,
    TwitchPredictionEndEvent,
    TwitchBanEvent,
    TwitchUnbanEvent,
    TwitchChatClearEvent,
    TwitchChatClearUserEvent,
    TwitchMessageDeleteEvent,
    TwitchIRCStatusEvent,
]


def _serialize_dict(event: object) -> dict[str, Any] | None:
    """Convierte un evento en diccionario {"type": ..., "data": ...}."""
    event_type = type(event)
    type_name = EVENT_TYPE_MAP.get(event_type)
    if type_name is None:
        return None

    try:
        data = asdict(event)  # type: ignore[call-overload]
        return {"type": type_name, "data": data}
    except Exception:
        LOGGER.exception("Error al serializar evento %s", event_type.__name__)
        return None


def _serialize(event: object) -> str | None:
    """Serializa un evento a JSON. Retorna None si el tipo no está mapeado."""
    payload = _serialize_dict(event)
    if payload is None:
        return None

    try:
        return json.dumps(payload)
    except Exception:
        LOGGER.exception("Error al codificar JSON del evento %s", type(event).__name__)
        return None


class WebSocketManager:
    """Gestiona las conexiones WebSocket activas y el broadcast de eventos."""

    def __init__(self, event_bus: EventBus, bot: Bot | None = None) -> None:
        self._event_bus = event_bus
        self._bot = bot
        self._connections: set[WebSocket] = set()
        self._registered = False

    def register(self) -> None:
        """Suscribe al EventBus para todos los tipos de evento. Llámalo una vez."""
        if self._registered:
            return
        self._registered = True
        for event_type in EVENT_TYPE_MAP:
            self._event_bus.subscribe(event_type, self._broadcast)

    async def _send_with_timeout(self, ws: WebSocket, message: str) -> WebSocket | None:
        """Envía mensaje a un cliente con timeout; retorna el cliente si falló."""
        with contextlib.suppress(Exception):
            if ws.client_state == WebSocketState.CONNECTED:
                await asyncio.wait_for(
                    ws.send_text(message), timeout=WS_SEND_TIMEOUT_SECONDS
                )
                return None
        return ws

    async def _send_to_all(self, message: str) -> None:
        """Envía un mensaje en paralelo a un snapshot de las conexiones activas."""
        clients = tuple(self._connections)
        if not clients:
            return

        results = await asyncio.gather(
            *(self._send_with_timeout(ws, message) for ws in clients)
        )
        dead = {ws for ws in results if ws is not None}
        if dead:
            self._connections -= dead

    async def _broadcast(self, event: object) -> None:
        """Envía el evento serializado a todas las conexiones activas."""
        if not self._connections:
            return

        message = _serialize(event)
        if message is None:
            return

        await self._send_to_all(message)

    async def broadcast_dev_reload(self) -> None:
        """Envía una señal dev_reload a todas las conexiones activas."""
        if not self._connections:
            return

        message = json.dumps({"type": "dev_reload"})
        await self._send_to_all(message)

    async def close_all(self) -> None:
        """Cierra activamente todas las conexiones WebSocket al apagar el servidor."""
        clients = tuple(self._connections)
        self._connections.clear()
        for ws in clients:
            with contextlib.suppress(Exception):
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.close(code=1001)

    async def handle(self, ws: WebSocket) -> None:
        """Maneja el ciclo de vida de una conexión WebSocket entrante."""
        origin = ws.headers.get("origin")
        if origin:
            origin_host = urlparse(origin).netloc
            host = ws.headers.get("host", "")
            if origin_host != host:
                LOGGER.warning(
                    "Conexión WebSocket rechazada por Origin inválido: %s (Host: %s)",
                    origin,
                    host,
                )
                await ws.close(code=WS_POLICY_VIOLATION_CODE)
                return

        if len(self._connections) >= MAX_WS_CLIENTS:
            LOGGER.warning(
                "Conexión WebSocket rechazada: límite de clientes alcanzado (%d)",
                MAX_WS_CLIENTS,
            )
            await ws.close(code=WS_POLICY_VIOLATION_CODE)
            return

        await ws.accept()
        self._connections.add(ws)
        LOGGER.info("WebSocket conectado. Clientes activos: %d", len(self._connections))

        try:
            # Enviar historial acumulado de la sesión actual en lote
            await self._send_history(ws)

            # Señal de fin de historial
            await ws.send_text(json.dumps({"type": "history_end"}))

            # Mantener la conexión abierta hasta que el cliente desconecte
            while True:
                data = await ws.receive_text()
                LOGGER.debug("Mensaje WS recibido (ignorado): %s", data[:100])

        except WebSocketDisconnect, asyncio.CancelledError:
            pass
        except Exception:
            LOGGER.exception("Error en WebSocket handler")
        finally:
            self._connections.discard(ws)
            LOGGER.info(
                "WebSocket desconectado. Clientes activos: %d", len(self._connections)
            )

    async def _send_history(self, ws: WebSocket) -> None:
        """Envía el historial acumulado del EventBus en un único lote al cliente."""
        all_events: list[object] = []
        for event_type in HISTORY_EVENT_TYPES:
            all_events.extend(self._event_bus.get_history(event_type))

        with contextlib.suppress(Exception):
            all_events.sort(key=lambda e: getattr(e, "timestamp", ""))

        batch: list[dict[str, Any]] = []
        for event in all_events:
            item = _serialize_dict(event)
            if item is not None:
                batch.append(item)

        if self._bot and self._bot.irc is not None:
            for join_event in list(self._bot.irc.connected_users.values()):
                item = _serialize_dict(join_event)
                if item is not None:
                    batch.append(item)

            for part_event in list(self._bot.irc.parted_users.values()):
                item = _serialize_dict(part_event)
                if item is not None:
                    batch.append(item)

        if batch:
            with contextlib.suppress(Exception):
                await ws.send_text(json.dumps({"type": "history_batch", "data": batch}))
