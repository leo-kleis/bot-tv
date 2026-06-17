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
