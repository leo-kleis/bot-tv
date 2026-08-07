from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


class UserMemoryCache:
    """Caché en memoria para identidades de usuarios y sus roles por canal."""

    def __init__(self) -> None:
        # user_id -> {username, display_name, is_bot, nickname, profile_image_url}
        self._users: dict[str, dict[str, Any]] = {}

        # username.lower() -> user_id
        self._username_map: dict[str, str] = {}

        # (channel_id, user_id) -> {is_moderator, is_vip, is_subscriber, sub_tier}
        self._channel_roles: dict[tuple[str, str], dict[str, Any]] = {}

    def preload(
        self,
        users_records: list[dict[str, Any]],
        channel_user_records: list[dict[str, Any]],
    ) -> None:
        """Carga masiva de la caché desde la base de datos al iniciar el bot."""
        self._users.clear()
        self._username_map.clear()
        self._channel_roles.clear()

        for record in users_records:
            uid = str(record["user_id"])
            uname = record["username"]
            self._users[uid] = {
                "user_id": uid,
                "username": uname,
                "display_name": record.get("display_name"),
                "is_bot": bool(record.get("is_bot", False)),
                "nickname": record.get("nickname"),
                "profile_image_url": record.get("profile_image_url"),
            }
            if uname:
                self._username_map[uname.lower()] = uid

        for record in channel_user_records:
            cid = str(record["channel_id"])
            uid = str(record["user_id"])
            self._channel_roles[(cid, uid)] = {
                "channel_id": cid,
                "user_id": uid,
                "followed_at": record.get("followed_at"),
                "unfollowed_at": record.get("unfollowed_at"),
                "is_moderator": bool(record.get("is_moderator", False)),
                "is_vip": bool(record.get("is_vip", False)),
                "is_subscriber": bool(record.get("is_subscriber", False)),
                "sub_tier": record.get("sub_tier"),
                "gifter_id": record.get("gifter_id"),
            }

        LOGGER.info(
            "Caché en memoria precargada con %d usuarios y %d asignaciones de roles.",
            len(self._users),
            len(self._channel_roles),
        )

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Devuelve la info de un usuario si existe en la caché."""
        return self._users.get(user_id)

    def get_user_id_by_name(self, username: str) -> str | None:
        """Busca el user_id por username en la caché."""
        return self._username_map.get(username.lower())

    def is_user_bot(self, user_id: str) -> bool:
        """Indica si el usuario está marcado como bot."""
        user = self._users.get(user_id)
        return user["is_bot"] if user else False

    def get_user_nickname(self, user_id: str) -> str | None:
        """Devuelve el nickname del usuario."""
        user = self._users.get(user_id)
        return user["nickname"] if user else None

    def get_profile_image_url(self, user_id: str) -> str | None:
        """Devuelve la URL del avatar del usuario."""
        user = self._users.get(user_id)
        return user["profile_image_url"] if user else None

    def get_user_roles(self, user_id: str, channel_id: str) -> dict[str, Any] | None:
        """Devuelve los roles del usuario en un canal dado."""
        if user_id not in self._users:
            return None
        roles = self._channel_roles.get((channel_id, user_id))
        if not roles:
            return {
                "is_moderator": False,
                "is_vip": False,
                "is_subscriber": False,
                "sub_tier": None,
            }
        return dict(roles)

    def needs_user_update(
        self,
        user_id: str,
        username: str,
        display_name: str | None = None,
    ) -> bool:
        """Determina si se requieren escrituras SQL en la tabla users."""
        user = self._users.get(user_id)
        if not user:
            return True
        return user["username"] != username or user["display_name"] != display_name

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
        roles = self._channel_roles.get((channel_id, user_id))
        if not roles:
            return True
        return (
            roles.get("is_moderator") != is_moderator
            or roles.get("is_vip") != is_vip
            or roles.get("is_subscriber") != is_subscriber
            or roles.get("sub_tier") != sub_tier
            or roles.get("gifter_id") != gifter_id
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
        if not user:
            user = {
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "is_bot": is_bot if is_bot is not None else False,
                "nickname": nickname,
                "profile_image_url": profile_image_url,
            }
            self._users[user_id] = user
        else:
            user["username"] = username
            user["display_name"] = display_name
            if is_bot is not None:
                user["is_bot"] = is_bot
            if nickname is not None:
                user["nickname"] = nickname
            if profile_image_url is not None:
                user["profile_image_url"] = profile_image_url

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
        roles = self._channel_roles.get((channel_id, user_id))
        if not roles:
            roles = {
                "channel_id": channel_id,
                "user_id": user_id,
                "followed_at": None,
                "unfollowed_at": None,
                "is_moderator": is_moderator,
                "is_vip": is_vip,
                "is_subscriber": is_subscriber,
                "sub_tier": sub_tier,
                "gifter_id": gifter_id,
            }
            self._channel_roles[(channel_id, user_id)] = roles
        else:
            roles["is_moderator"] = is_moderator
            roles["is_vip"] = is_vip
            roles["is_subscriber"] = is_subscriber
            roles["sub_tier"] = sub_tier
            roles["gifter_id"] = gifter_id

    def set_nickname(self, user_id: str, nickname: str | None) -> None:
        """Establece o elimina el apodo en la caché."""
        user = self._users.get(user_id)
        if user:
            user["nickname"] = nickname

    def set_user_bot(self, user_id: str, is_bot: bool) -> None:
        """Actualiza el estado is_bot en la caché."""
        user = self._users.get(user_id)
        if user:
            user["is_bot"] = is_bot

    def set_profile_image_url(self, user_id: str, url: str) -> None:
        """Actualiza la URL del avatar en la caché."""
        user = self._users.get(user_id)
        if user:
            user["profile_image_url"] = url

    def get_follower_ids(self, channel_id: str) -> set[str]:
        """Devuelve el conjunto de user_id que siguen al canal en la caché."""
        cid = channel_id
        return {
            uid
            for (c, uid), roles in self._channel_roles.items()
            if c == cid and roles.get("followed_at") and not roles.get("unfollowed_at")
        }

    def sync_followers(
        self,
        channel_id: str,
        new_followers: list[tuple[str, str, str | None]],
        unfollowed_ids: list[str] | None = None,
        now_iso: str | None = None,
    ) -> None:
        """Sincroniza los cambios de seguidores en la caché."""
        cid = channel_id

        if unfollowed_ids:
            for uid in unfollowed_ids:
                roles = self._channel_roles.get((cid, uid))
                if roles:
                    roles["unfollowed_at"] = now_iso

        if new_followers:
            for uid, uname, fat in new_followers:
                self.update_user(uid, uname)
                roles = self._channel_roles.get((cid, uid))
                if not roles:
                    self._channel_roles[(cid, uid)] = {
                        "channel_id": cid,
                        "user_id": uid,
                        "followed_at": fat,
                        "unfollowed_at": None,
                        "is_moderator": False,
                        "is_vip": False,
                        "is_subscriber": False,
                        "sub_tier": None,
                        "gifter_id": None,
                    }
                else:
                    roles["followed_at"] = fat
                    roles["unfollowed_at"] = None

    def list_users_with_filters(
        self,
        channel_id: str,
        broadcaster_id: str | None = None,
        role: str | None = None,
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
        """Filtra y pagina los usuarios almacenados en la caché en memoria."""
        cid = channel_id
        matching_users: list[dict[str, Any]] = []

        role_clean = role.lower() if role else None
        search_clean = username_search.lower() if username_search else None

        for uid, user in self._users.items():
            roles = self._channel_roles.get((cid, uid), {})

            # 1. Filtro por Rol
            if role_clean:
                if role_clean in ("bot", "bots") and not user.get("is_bot"):
                    continue
                if role_clean in (
                    "moderator",
                    "moderador",
                    "mods",
                    "mod",
                ) and not roles.get("is_moderator"):
                    continue
                if role_clean in ("vip", "vips") and not roles.get("is_vip"):
                    continue
                if role_clean in (
                    "subscriber",
                    "suscriptor",
                    "subscribers",
                    "sub",
                    "subs",
                ) and not roles.get("is_subscriber"):
                    continue

            # 2. Búsqueda por Nombre / Apodo
            if search_clean:
                u_name = user.get("username", "").lower()
                d_name = (user.get("display_name") or "").lower()
                n_name = (user.get("nickname") or "").lower()
                if (
                    search_clean not in u_name
                    and search_clean not in d_name
                    and search_clean not in n_name
                ):
                    continue

            followed_at = roles.get("followed_at")
            unfollowed_at = roles.get("unfollowed_at")

            # 3. Filtros por Fecha
            if followed_after and (not followed_at or followed_at < followed_after):
                continue
            if followed_before and (not followed_at or followed_at > followed_before):
                continue
            if unfollowed_after and (
                not unfollowed_at or unfollowed_at < unfollowed_after
            ):
                continue
            if unfollowed_before and (
                not unfollowed_at or unfollowed_at > unfollowed_before
            ):
                continue

            # 4. Filtro por Estado de Seguidor
            if is_follower and is_follower in (
                "follower",
                "not_follower",
                "unfollower",
            ):
                if broadcaster_id and uid == broadcaster_id:
                    continue

                if is_follower == "follower":
                    if not (followed_at and not unfollowed_at):
                        continue
                elif is_follower == "not_follower":
                    if followed_at is not None:
                        continue
                elif is_follower == "unfollower" and not unfollowed_at:
                    continue

            matching_users.append(
                {
                    "user_id": uid,
                    "username": user.get("username", ""),
                    "display_name": user.get("display_name"),
                    "nickname": user.get("nickname"),
                    "is_bot": bool(user.get("is_bot", False)),
                    "is_moderator": bool(roles.get("is_moderator", False)),
                    "is_vip": bool(roles.get("is_vip", False)),
                    "is_subscriber": bool(roles.get("is_subscriber", False)),
                    "sub_tier": roles.get("sub_tier"),
                    "followed_at": followed_at,
                    "unfollowed_at": unfollowed_at,
                }
            )

        # Ordenar los usuarios según sort_by y sort_order
        rev = sort_order.lower() == "desc"
        sb = sort_by.lower()

        if sb == "role":

            def _role_rank(u: dict[str, Any]) -> int:
                if u.get("is_moderator"):
                    return 1
                if u.get("is_vip"):
                    return 2
                if u.get("is_subscriber"):
                    return 3
                if u.get("is_bot"):
                    return 4
                return 5

            matching_users.sort(
                key=lambda u: (_role_rank(u), u["username"].lower()),
                reverse=rev,
            )
        elif sb == "follow_date":
            if rev:
                matching_users.sort(
                    key=lambda u: (
                        1 if (u.get("unfollowed_at") or u.get("followed_at")) else 0,
                        u.get("unfollowed_at") or u.get("followed_at") or "",
                        u["username"].lower(),
                    ),
                    reverse=True,
                )
            else:
                matching_users.sort(
                    key=lambda u: (
                        0 if (u.get("unfollowed_at") or u.get("followed_at")) else 1,
                        u.get("unfollowed_at") or u.get("followed_at") or "",
                        u["username"].lower(),
                    ),
                    reverse=False,
                )
        else:
            matching_users.sort(
                key=lambda u: (u.get("display_name") or u["username"]).lower(),
                reverse=rev,
            )

        total_count = len(matching_users)
        limit_val = max(1, limit)
        offset_val = max(0, offset)
        page_users = matching_users[offset_val : offset_val + limit_val]

        return page_users, total_count
