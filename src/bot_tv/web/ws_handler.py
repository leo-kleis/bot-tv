"""WebSocket handler: consume el EventBus y transmite eventos a clientes web."""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import asdict
from typing import TYPE_CHECKING

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


def _serialize(event: object) -> str | None:
    """Serializa un evento a JSON. Retorna None si el tipo no está mapeado."""
    event_type = type(event)
    type_name = EVENT_TYPE_MAP.get(event_type)
    if type_name is None:
        return None

    try:
        data = asdict(event)  # type: ignore[call-overload]
        # color_rgb es tuple — asdict lo convierte a list, lo dejamos así
        return json.dumps({"type": type_name, "data": data})
    except Exception:
        LOGGER.exception("Error al serializar evento %s", event_type.__name__)
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

    async def _broadcast(self, event: object) -> None:
        """Envía el evento serializado a todas las conexiones activas."""
        if not self._connections:
            return

        message = _serialize(event)
        if message is None:
            return

        dead: set[WebSocket] = set()
        for ws in self._connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
                else:
                    dead.add(ws)
            except Exception:
                dead.add(ws)

        self._connections -= dead

    async def broadcast_dev_reload(self) -> None:
        """Envía una señal dev_reload a todas las conexiones activas."""
        if not self._connections:
            return

        message = json.dumps({"type": "dev_reload"})
        dead: set[WebSocket] = set()
        for ws in self._connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
                else:
                    dead.add(ws)
            except Exception:
                dead.add(ws)

        self._connections -= dead

    async def handle(self, ws: WebSocket) -> None:
        """Maneja el ciclo de vida de una conexión WebSocket entrante."""
        await ws.accept()
        self._connections.add(ws)
        LOGGER.info("WebSocket conectado. Clientes activos: %d", len(self._connections))

        try:
            # Enviar historial acumulado de la sesión actual
            await self._send_history(ws)

            # Señal de fin de historial
            await ws.send_text(json.dumps({"type": "history_end"}))

            # Mantener la conexión abierta hasta que el cliente desconecte
            while True:
                # Leer mensajes del cliente (por ahora no los procesamos,
                # las acciones van por REST API)
                data = await ws.receive_text()
                LOGGER.debug("Mensaje WS recibido (ignorado): %s", data[:100])

        except WebSocketDisconnect:
            pass
        except Exception:
            LOGGER.exception("Error en WebSocket handler")
        finally:
            self._connections.discard(ws)
            LOGGER.info(
                "WebSocket desconectado. Clientes activos: %d", len(self._connections)
            )

    async def _send_history(self, ws: WebSocket) -> None:
        """Envía el historial acumulado del EventBus al cliente recién conectado."""
        all_events: list[object] = []
        for event_type in HISTORY_EVENT_TYPES:
            all_events.extend(self._event_bus.get_history(event_type))

        # Ordenar por timestamp
        with contextlib.suppress(Exception):
            all_events.sort(key=lambda e: getattr(e, "timestamp", ""))

        for event in all_events:
            message = _serialize(event)
            if message:
                try:
                    await ws.send_text(message)
                except Exception:
                    break

        # Enviar usuarios conectados y desconectados actualmente en IRC
        if self._bot and self._bot.irc is not None:
            for join_event in list(self._bot.irc.connected_users.values()):
                message = _serialize(join_event)
                if message:
                    try:
                        await ws.send_text(message)
                    except Exception:
                        break

            for part_event in list(self._bot.irc.parted_users.values()):
                message = _serialize(part_event)
                if message:
                    try:
                        await ws.send_text(message)
                    except Exception:
                        break
