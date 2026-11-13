from __future__ import annotations

import logging
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from bot_tv.database.repositories.base import to_iso_str, to_utc_datetime

if TYPE_CHECKING:
    import asyncpg

LOGGER = logging.getLogger(__name__)

_EPOCH_UTC = datetime.min.replace(tzinfo=UTC)
_BOT_ROLES = frozenset({"bot", "bots"})
_MOD_ROLES = frozenset({"moderator", "moderador", "mods", "mod"})
_VIP_ROLES = frozenset({"vip", "vips"})
_SUB_ROLES = frozenset({"subscriber", "suscriptor", "subscribers", "sub", "subs"})
_FOLLOWER_STATES = frozenset({"follower", "not_follower", "unfollower"})


@dataclass(slots=True)
class _CachedUser:
    """Representación compacta en memoria de un registro de usuario."""

    user_id: str
    username: str
    display_name: str | None
    is_bot: bool
    nickname: str | None
    profile_image_url: str | None

    def to_dict(self) -> dict[str, Any]:
        """Materializa el diccionario público esperado por los consumidores."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "is_bot": self.is_bot,
            "nickname": self.nickname,
            "profile_image_url": self.profile_image_url,
        }


@dataclass(slots=True)
class _CachedChannelRole:
    """Representación compacta en memoria de roles y seguimiento por canal."""

    followed_at: datetime | None = None
    unfollowed_at: datetime | None = None
    is_moderator: bool = False
    is_vip: bool = False
    is_subscriber: bool = False
    sub_tier: str | None = None
    gifter_id: str | None = None


def _role_rank(user: _CachedUser, roles: _CachedChannelRole | None) -> int:
    """Calcula la prioridad numérica de rol para ordenamiento."""
    if roles is not None:
        if roles.is_moderator:
            return 1
        if roles.is_vip:
            return 2
        if roles.is_subscriber:
            return 3
    if user.is_bot:
        return 4
    return 5


def _follow_sort_key(
    roles: _CachedChannelRole | None,
    username: str,
    *,
    reverse: bool,
) -> tuple[int, datetime, str]:
    """Construye la clave de ordenamiento por fecha manteniendo nulos al final."""
    dt = (roles.unfollowed_at or roles.followed_at) if roles is not None else None
    has_dt = 1 if dt is not None else 0
    null_bucket = has_dt if reverse else (1 - has_dt)
    return (null_bucket, dt or _EPOCH_UTC, username.lower())


class UserMemoryCache:
    """Caché en memoria para identidades de usuarios y sus roles por canal."""

    def __init__(self) -> None:
        self._users: dict[str, _CachedUser] = {}
        self._username_map: dict[str, str] = {}
        # Agrupar por channel_id evita millones/miles de tuplas clave en memoria.
        self._channel_roles: dict[str, dict[str, _CachedChannelRole]] = {}

    @property
    def has_users(self) -> bool:
        """Indica si la caché ya contiene usuarios precargados o insertados."""
        return bool(self._users)

    def _get_channel_map(
        self, channel_id: str, *, create: bool = False
    ) -> dict[str, _CachedChannelRole] | None:
        """Obtiene (o inicializa) el mapa de roles de un canal internando su ID."""
        channel_map = self._channel_roles.get(channel_id)
        if channel_map is None and create:
            interned_cid = sys.intern(channel_id)
            channel_map = {}
            self._channel_roles[interned_cid] = channel_map
        return channel_map

    def _get_role(self, channel_id: str, user_id: str) -> _CachedChannelRole | None:
        """Busca los roles de un usuario dentro de un canal concreto."""
        channel_map = self._channel_roles.get(channel_id)
        if channel_map is None:
            return None
        return channel_map.get(user_id)

    def preload(
        self,
        users_records: Sequence[Mapping[str, Any] | asyncpg.Record],
        channel_user_records: Sequence[Mapping[str, Any] | asyncpg.Record],
    ) -> None:
        """Carga masiva de la caché desde la base de datos al iniciar el bot."""
        self._users.clear()
        self._username_map.clear()
        self._channel_roles.clear()

        for record in users_records:
            uid = str(record["user_id"])
            uname = str(record["username"] or "")
            self._users[uid] = _CachedUser(
                user_id=uid,
                username=uname,
                display_name=record.get("display_name"),
                is_bot=bool(record.get("is_bot", False)),
                nickname=record.get("nickname"),
                profile_image_url=record.get("profile_image_url"),
            )
            if uname:
                self._username_map[uname.lower()] = uid

        total_roles = 0
        for record in channel_user_records:
            cid = str(record["channel_id"])
            uid = str(record["user_id"])
            raw_tier = record.get("sub_tier")
            sub_tier = sys.intern(raw_tier) if isinstance(raw_tier, str) else None
            channel_map = self._get_channel_map(cid, create=True)
            if channel_map is not None:
                channel_map[uid] = _CachedChannelRole(
                    followed_at=to_utc_datetime(record.get("followed_at")),
                    unfollowed_at=to_utc_datetime(record.get("unfollowed_at")),
                    is_moderator=bool(record.get("is_moderator", False)),
                    is_vip=bool(record.get("is_vip", False)),
                    is_subscriber=bool(record.get("is_subscriber", False)),
                    sub_tier=sub_tier,
                    gifter_id=record.get("gifter_id"),
                )
                total_roles += 1

        LOGGER.info(
            "Caché en memoria precargada con %d usuarios y %d asignaciones de roles.",
            len(self._users),
            total_roles,
        )

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Devuelve la info de un usuario si existe en la caché."""
        user = self._users.get(user_id)
        return user.to_dict() if user is not None else None

    def get_user_id_by_name(self, username: str) -> str | None:
        """Busca el user_id por username en la caché."""
        return self._username_map.get(username.lower())

    def is_user_bot(self, user_id: str) -> bool:
        """Indica si el usuario está marcado como bot."""
        user = self._users.get(user_id)
        return user.is_bot if user is not None else False

    def get_user_nickname(self, user_id: str) -> str | None:
        """Devuelve el nickname del usuario."""
        user = self._users.get(user_id)
        return user.nickname if user is not None else None

    def get_profile_image_url(self, user_id: str) -> str | None:
        """Devuelve la URL del avatar del usuario."""
        user = self._users.get(user_id)
        return user.profile_image_url if user is not None else None

    def get_user_roles(self, user_id: str, channel_id: str) -> dict[str, Any] | None:
        """Devuelve los roles del usuario en un canal dado."""
        if user_id not in self._users:
            return None
        roles = self._get_role(channel_id, user_id)
        if roles is None:
            return {
                "is_moderator": False,
                "is_vip": False,
                "is_subscriber": False,
                "sub_tier": None,
            }
        return {
            "channel_id": channel_id,
            "user_id": user_id,
            "followed_at": to_iso_str(roles.followed_at),
            "unfollowed_at": to_iso_str(roles.unfollowed_at),
            "is_moderator": roles.is_moderator,
            "is_vip": roles.is_vip,
            "is_subscriber": roles.is_subscriber,
            "sub_tier": roles.sub_tier,
            "gifter_id": roles.gifter_id,
        }

    def get_display_role(
        self,
        user_id: str | None,
        broadcaster_id: str | int,
        bot_id: str | None = None,
    ) -> str:
        """Determina la etiqueta de rol de un usuario en el canal desde la caché."""
        if not user_id:
            return "Visita"

        bid_str = str(broadcaster_id)
        if user_id == bid_str:
            return "Broadcaster"

        if (bot_id and user_id == bot_id) or self.is_user_bot(user_id):
            return "Bot"

        if user_id not in self._users:
            return "Visita"

        roles = self._get_role(bid_str, user_id)
        if (
            roles is not None
            and roles.followed_at is not None
            and roles.unfollowed_at is None
        ):
            return roles.followed_at.astimezone().strftime("%d/%m/%y")

        return "Visita"

    def get_user_detail_by_name(
        self, username: str, channel_id: str
    ) -> dict[str, Any] | None:
        """Obtiene el detalle consolidado de un usuario y su rol desde la caché."""
        uid = self._username_map.get(username.lower())
        if not uid:
            return None
        user = self._users.get(uid)
        if user is None:
            return None
        roles = self._get_role(channel_id, uid)
        return {
            "user_id": uid,
            "username": user.username or username,
            "display_name": user.display_name,
            "nickname": user.nickname,
            "is_bot": user.is_bot,
            "is_moderator": roles.is_moderator if roles else False,
            "is_vip": roles.is_vip if roles else False,
            "is_subscriber": roles.is_subscriber if roles else False,
            "sub_tier": roles.sub_tier if roles else None,
            "followed_at": to_iso_str(roles.followed_at) if roles else None,
            "unfollowed_at": to_iso_str(roles.unfollowed_at) if roles else None,
        }

    def search_users(
        self,
        q: str,
        limit: int = 10,
        channel_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Busca usuarios en la caché en memoria para autocompletado instantáneo."""
        q_clean = q.strip().lower()
        if not q_clean:
            return []

        channel_map = self._channel_roles.get(channel_id) if channel_id else None
        matches: list[tuple[_CachedUser, _CachedChannelRole | None]] = []

        for user in self._users.values():
            u_name = user.username.lower()
            d_name = (user.display_name or "").lower()
            n_name = (user.nickname or "").lower()
            if (
                q_clean not in u_name
                and q_clean not in d_name
                and q_clean not in n_name
            ):
                continue

            roles: _CachedChannelRole | None = None
            if channel_id:
                if channel_map is not None:
                    roles = channel_map.get(user.user_id)
            else:
                for ch_map in self._channel_roles.values():
                    roles = ch_map.get(user.user_id)
                    if roles is not None:
                        break
            matches.append((user, roles))

        matches.sort(
            key=lambda pair: (pair[0].display_name or pair[0].username).lower()
        )
        page = matches[: max(1, limit)]
        return [
            {
                "user_id": user.user_id,
                "username": user.username,
                "display_name": user.display_name,
                "nickname": user.nickname or "",
                "is_bot": user.is_bot,
                "is_moderator": roles.is_moderator if roles else False,
                "is_vip": roles.is_vip if roles else False,
                "is_subscriber": roles.is_subscriber if roles else False,
                "is_follower": (
                    roles is not None
                    and roles.followed_at is not None
                    and roles.unfollowed_at is None
                ),
            }
            for user, roles in page
        ]

    def needs_user_update(
        self,
        user_id: str,
        username: str,
        display_name: str | None = None,
    ) -> bool:
        """Determina si se requieren escrituras SQL en la tabla users."""
        user = self._users.get(user_id)
        if user is None:
            return True
        return user.username != username or user.display_name != display_name

    def needs_roles_update(
        self,
        channel_id: str,
        user_id: str,
        is_moderator: bool,
        is_vip: bool,
        is_subscriber: bool,
        sub_tier: str | None = None,
        gifter_id: str | None = None,
    ) -> bool:
        """Determina si se requieren escrituras SQL en la tabla channel_users."""
        roles = self._get_role(channel_id, user_id)
        if roles is None:
            return True
        return (
            roles.is_moderator != is_moderator
            or roles.is_vip != is_vip
            or roles.is_subscriber != is_subscriber
            or roles.sub_tier != sub_tier
            or roles.gifter_id != gifter_id
        )

    def update_user(
        self,
        user_id: str,
        username: str,
        display_name: str | None = None,
        is_bot: bool | None = None,
        nickname: str | None = None,
        profile_image_url: str | None = None,
    ) -> None:
        """Actualiza o crea un registro de usuario en la caché."""
        user = self._users.get(user_id)
        if user is None:
            self._users[user_id] = _CachedUser(
                user_id=user_id,
                username=username,
                display_name=display_name,
                is_bot=is_bot if is_bot is not None else False,
                nickname=nickname,
                profile_image_url=profile_image_url,
            )
        else:
            old_username = user.username
            if old_username and username and old_username.lower() != username.lower():
                self._username_map.pop(old_username.lower(), None)
            user.username = username
            if display_name is not None:
                user.display_name = display_name
            if is_bot is not None:
                user.is_bot = is_bot
            if nickname is not None:
                user.nickname = nickname
            if profile_image_url is not None:
                user.profile_image_url = profile_image_url

        if username:
            self._username_map[username.lower()] = user_id

    def update_roles(
        self,
        channel_id: str,
        user_id: str,
        is_moderator: bool,
        is_vip: bool,
        is_subscriber: bool,
        sub_tier: str | None = None,
        gifter_id: str | None = None,
    ) -> None:
        """Actualiza los roles de un usuario para un canal en la caché."""
        tier = sys.intern(sub_tier) if isinstance(sub_tier, str) else None
        channel_map = self._get_channel_map(channel_id, create=True)
        if channel_map is None:
            return
        roles = channel_map.get(user_id)
        if roles is None:
            channel_map[user_id] = _CachedChannelRole(
                is_moderator=is_moderator,
                is_vip=is_vip,
                is_subscriber=is_subscriber,
                sub_tier=tier,
                gifter_id=gifter_id,
            )
        else:
            roles.is_moderator = is_moderator
            roles.is_vip = is_vip
            roles.is_subscriber = is_subscriber
            roles.sub_tier = tier
            roles.gifter_id = gifter_id

    def set_nickname(self, user_id: str, nickname: str | None) -> None:
        """Establece o elimina el apodo en la caché."""
        user = self._users.get(user_id)
        if user is not None:
            user.nickname = nickname

    def set_user_bot(self, user_id: str, is_bot: bool) -> None:
        """Actualiza el estado is_bot en la caché."""
        user = self._users.get(user_id)
        if user is not None:
            user.is_bot = is_bot

    def set_profile_image_url(self, user_id: str, url: str) -> None:
        """Actualiza la URL del avatar en la caché."""
        user = self._users.get(user_id)
        if user is not None:
            user.profile_image_url = url

    def get_follower_ids(self, channel_id: str) -> set[str]:
        """Devuelve el conjunto de user_id que siguen al canal en la caché."""
        channel_map = self._channel_roles.get(channel_id)
        if channel_map is None:
            return set()
        return {
            uid
            for uid, roles in channel_map.items()
            if roles.followed_at is not None and roles.unfollowed_at is None
        }

    def set_user_follow_status(
        self, channel_id: str, user_id: str, followed_at: datetime | str | None
    ) -> None:
        """Actualiza el estado de seguimiento de un usuario en un canal en la caché."""
        dt_followed = to_utc_datetime(followed_at)
        channel_map = self._get_channel_map(channel_id, create=True)
        if channel_map is None:
            return
        roles = channel_map.get(user_id)
        if roles is None:
            channel_map[user_id] = _CachedChannelRole(
                followed_at=dt_followed,
                unfollowed_at=None,
            )
        else:
            roles.followed_at = dt_followed
            roles.unfollowed_at = None

    def sync_followers(
        self,
        channel_id: str,
        new_followers: list[tuple[str, str, str | None]],
        unfollowed_ids: list[str] | None = None,
        now_iso: str | None = None,
    ) -> None:
        """Sincroniza los cambios de seguidores en la caché."""
        channel_map = self._get_channel_map(channel_id, create=True)
        if channel_map is None:
            return

        if unfollowed_ids:
            dt_now = to_utc_datetime(now_iso)
            for uid in unfollowed_ids:
                roles = channel_map.get(uid)
                if roles is not None:
                    roles.unfollowed_at = dt_now

        if new_followers:
            for uid, uname, fat in new_followers:
                self.update_user(uid, uname)
                dt_followed = to_utc_datetime(fat)
                roles = channel_map.get(uid)
                if roles is None:
                    channel_map[uid] = _CachedChannelRole(
                        followed_at=dt_followed,
                        unfollowed_at=None,
                    )
                else:
                    roles.followed_at = dt_followed
                    roles.unfollowed_at = None

    def list_users_with_filters(
        self,
        channel_id: str,
        broadcaster_id: str | None = None,
        role: str | None = None,
        has_nickname: bool | None = None,
        username_search: str | None = None,
        followed_after: str | None = None,
        followed_before: str | None = None,
        unfollowed_after: str | None = None,
        unfollowed_before: str | None = None,
        is_follower: str | None = None,
        sort_by: str = "username",
        sort_order: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Filtra y pagina usuarios materializando dicts solo para la página."""
        channel_map = self._channel_roles.get(channel_id)
        role_clean = role.lower() if role else None
        search_clean = username_search.lower() if username_search else None
        follower_filter = is_follower if is_follower in _FOLLOWER_STATES else None

        dt_followed_after = to_utc_datetime(followed_after)
        dt_followed_before = to_utc_datetime(followed_before)
        dt_unfollowed_after = to_utc_datetime(unfollowed_after)
        dt_unfollowed_before = to_utc_datetime(unfollowed_before)

        matches: list[tuple[_CachedUser, _CachedChannelRole | None]] = []

        for uid, user in self._users.items():
            roles = channel_map.get(uid) if channel_map is not None else None

            if role_clean:
                if role_clean in _BOT_ROLES and not user.is_bot:
                    continue
                if role_clean in _MOD_ROLES and not (roles and roles.is_moderator):
                    continue
                if role_clean in _VIP_ROLES and not (roles and roles.is_vip):
                    continue
                if role_clean in _SUB_ROLES and not (roles and roles.is_subscriber):
                    continue

            if has_nickname is not None and bool(user.nickname) != has_nickname:
                continue

            if search_clean:
                u_name = user.username.lower()
                d_name = (user.display_name or "").lower()
                n_name = (user.nickname or "").lower()
                if (
                    search_clean not in u_name
                    and search_clean not in d_name
                    and search_clean not in n_name
                ):
                    continue

            followed_at = roles.followed_at if roles is not None else None
            unfollowed_at = roles.unfollowed_at if roles is not None else None

            if dt_followed_after is not None and (
                followed_at is None or followed_at < dt_followed_after
            ):
                continue
            if dt_followed_before is not None and (
                followed_at is None or followed_at > dt_followed_before
            ):
                continue
            if dt_unfollowed_after is not None and (
                unfollowed_at is None or unfollowed_at < dt_unfollowed_after
            ):
                continue
            if dt_unfollowed_before is not None and (
                unfollowed_at is None or unfollowed_at > dt_unfollowed_before
            ):
                continue

            if follower_filter is not None:
                if broadcaster_id and uid == broadcaster_id:
                    continue
                if follower_filter == "follower":
                    if followed_at is None or unfollowed_at is not None:
                        continue
                elif follower_filter == "not_follower":
                    if followed_at is not None:
                        continue
                elif follower_filter == "unfollower" and unfollowed_at is None:
                    continue

            matches.append((user, roles))

        rev = sort_order.lower() == "desc"
        sb = sort_by.lower()

        if sb == "role":
            matches.sort(
                key=lambda pair: (
                    _role_rank(pair[0], pair[1]),
                    pair[0].username.lower(),
                ),
                reverse=rev,
            )
        elif sb == "follow_date":
            matches.sort(
                key=lambda pair: _follow_sort_key(
                    pair[1], pair[0].username, reverse=rev
                ),
                reverse=rev,
            )
        else:
            matches.sort(
                key=lambda pair: (pair[0].display_name or pair[0].username).lower(),
                reverse=rev,
            )

        total_count = len(matches)
        limit_val = max(1, limit)
        offset_val = max(0, offset)
        page_refs = matches[offset_val : offset_val + limit_val]

        page_users = [
            {
                "user_id": user.user_id,
                "username": user.username,
                "display_name": user.display_name,
                "nickname": user.nickname,
                "is_bot": user.is_bot,
                "is_moderator": roles.is_moderator if roles else False,
                "is_vip": roles.is_vip if roles else False,
                "is_subscriber": roles.is_subscriber if roles else False,
                "sub_tier": roles.sub_tier if roles else None,
                "followed_at": to_iso_str(roles.followed_at) if roles else None,
                "unfollowed_at": to_iso_str(roles.unfollowed_at) if roles else None,
            }
            for user, roles in page_refs
        ]

        return page_users, total_count
