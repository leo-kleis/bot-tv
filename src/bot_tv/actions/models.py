"""Dataclasses de retorno para las acciones del bot."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UserResolveResult:
    """Resultado de la resolución de un usuario."""

    user_id: str | None
    found_locally: bool
    found_on_twitch: bool
    error: str | None = None


@dataclass
class BotToggleResult:
    """Resultado de marcar/desmarcar un usuario como bot."""

    username: str
    is_bot: bool  # estado NUEVO (después del toggle)
    user_id: str


@dataclass
class NicknameResult:
    """Resultado de asignar/eliminar un apodo."""

    username: str
    nickname: str | None  # None = eliminado


@dataclass
class UserRolesResult:
    """Resultado de actualizar los roles de un usuario."""

    username: str
    user_id: str
    is_bot: bool
    is_moderator: bool
    is_vip: bool
    is_subscriber: bool
    sub_tier: str | None = None  # "1000" | "2000" | "3000"
    gifter_id: str | None = None  # user_id de quien regaló la sub


@dataclass
class SyncFollowersResult:
    """Resultado de una sincronización de seguidores."""

    channel: str
    ok: bool
    error: str | None = None


@dataclass
class ModelInfo:
    """Info de un modelo disponible."""

    name: str
    display_name: str
    enabled: bool
    rpm_limit: int
    rpd_limit: int


@dataclass
class AgentTalkResult:
    """Resultado de una consulta al agente."""

    response: str
    model: str
