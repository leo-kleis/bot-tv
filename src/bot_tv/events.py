"""Eventos tipados del sistema.

Cada evento contiene datos puros (sin markup Rich ni colores de terminal).
Los consumers son responsables de formatear la presentación.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat()


# ── Chat ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ChatMessageEvent:
    """Mensaje de chat recibido en el canal."""

    user_id: str
    username: str
    display_name: str
    nickname: str | None
    color_rgb: tuple[int, int, int]
    role: str  # "Broadcaster", "Bot", "Visita", "DD/MM/AA"
    text: str
    channel_id: str
    is_bot: bool
    timestamp: str = field(default_factory=_now)


# ── IRC (JOIN/PART) ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class UserJoinEvent:
    """Usuario se unió al canal (IRC JOIN)."""

    user_id: str | None
    username: str
    display_name: str
    nickname: str | None
    color_rgb: tuple[int, int, int]
    role: str
    is_bot: bool = False
    is_moderator: bool = False
    is_vip: bool = False
    is_subscriber: bool = False
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class UserPartEvent:
    """Usuario salió del canal (IRC PART)."""

    user_id: str | None
    username: str
    display_name: str
    nickname: str | None
    color_rgb: tuple[int, int, int]
    role: str
    timestamp: str = field(default_factory=_now)


# ── Stream ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class StreamOnlineEvent:
    """El stream se puso online."""

    broadcaster_name: str
    title: str
    category: str
    started_at: str | None = None
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class StreamOfflineEvent:
    """El stream se puso offline."""

    broadcaster_name: str
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class ViewerUpdateEvent:
    """Actualización del conteo de viewers."""

    count: int
    diff: int | None  # None si es el primer valor conocido
    timestamp: str = field(default_factory=_now)


# ── Seguidores ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FollowerSyncEvent:
    """Resultado de una sincronización de seguidores."""

    new_count: int
    lost_count: int
    total: int
    new_labels: list[str]
    lost_labels: list[str]
    is_first_sync: bool
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class FollowerProgressEvent:
    """Progreso de obtención de seguidores desde la API."""

    count: int
    total: int
    timestamp: str = field(default_factory=_now)


# ── Agente ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AgentResponseEvent:
    """Respuesta del agente de IA a una consulta."""

    question: str
    response: str
    model: str
    timestamp: str = field(default_factory=_now)


# ── Clips ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ClipCreatedEvent:
    """Clip creado con éxito."""

    url: str
    broadcaster_name: str
    timestamp: str = field(default_factory=_now)


# ── Logs del bot ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class BotLogEvent:
    """Entrada de log del sistema del bot."""

    level: str  # "INFO", "WARNING", "ERROR", "CRITICAL"
    module: str
    message: str
    timestamp: str = field(default_factory=_now)


# ── Twitch EventSub Alerts ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TwitchRaidEvent:
    """Evento que representa una raid recibida."""

    from_username: str
    from_display_name: str
    viewer_count: int
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchSubscribeEvent:
    """Evento que representa una nueva suscripción."""

    username: str
    display_name: str
    tier: str  # "1000", "2000", "3000"
    is_gift: bool
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchSubscriptionGiftEvent:
    """Evento que representa el regalo de suscripciones."""

    username: str | None  # None si es anónimo
    display_name: str | None
    tier: str
    total: int
    cumulative_total: int | None
    is_anonymous: bool
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchSubscriptionMessageEvent:
    """Evento que representa un mensaje de resuscripción."""

    username: str
    display_name: str
    tier: str
    cumulative_months: int
    streak_months: int | None
    message: str
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchCheerEvent:
    """Evento que representa un cheer (donación de bits)."""

    username: str | None  # None si es anónimo
    display_name: str | None
    bits: int
    message: str
    is_anonymous: bool
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchChannelPointsRedeemEvent:
    """Evento que representa el canje de puntos de canal."""

    username: str
    display_name: str
    reward_title: str
    reward_cost: int
    user_input: str
    timestamp: str = field(default_factory=_now)


# Predicciones
@dataclass(frozen=True, slots=True)
class TwitchPredictionBeginEvent:
    """Evento de inicio de una predicción."""

    title: str
    outcomes: list[str]
    locks_at: str
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchPredictionProgressEvent:
    """Evento de progreso en una predicción."""

    title: str
    outcomes_votes: list[tuple[str, int, int]]  # (opción, votos, puntos)
    locks_at: str
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchPredictionLockEvent:
    """Evento de bloqueo de una predicción."""

    title: str
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchPredictionEndEvent:
    """Evento de finalización de una predicción."""

    title: str
    status: str  # "resolved" o "canceled"
    winning_outcome_title: str | None
    timestamp: str = field(default_factory=_now)


# Moderación
@dataclass(frozen=True, slots=True)
class TwitchBanEvent:
    """Evento de ban o timeout de un usuario."""

    username: str
    display_name: str
    moderator_name: str
    reason: str | None
    permanent: bool
    duration_seconds: int | None
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchUnbanEvent:
    """Evento de desbaneo de un usuario."""

    username: str
    display_name: str
    moderator_name: str
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchChatClearEvent:
    """Evento que se dispara cuando se limpia el chat."""

    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchChatClearUserEvent:
    """Evento que se dispara cuando se purgan los mensajes de un usuario."""

    username: str
    display_name: str
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchMessageDeleteEvent:
    """Evento que representa la eliminación de un mensaje individual."""

    username: str
    display_name: str
    message_text: str
    timestamp: str = field(default_factory=_now)


@dataclass(frozen=True, slots=True)
class TwitchIRCStatusEvent:
    """Evento que indica el cambio de estado de conexión del IRC."""

    connected: bool
    timestamp: str = field(default_factory=_now)
