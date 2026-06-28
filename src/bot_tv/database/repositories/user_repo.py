from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bot_tv.database.repositories.base import BaseRepository

if TYPE_CHECKING:
    import sqlite3


class UserRepository(BaseRepository):
    """Repositorio para gestionar las operaciones sobre la tabla users."""

    async def upsert_user(
        self,
        user_id: str,
        username: str,
        display_name: str | None = None,
        is_moderator: bool | None = None,
        is_vip: bool | None = None,
        is_subscriber: bool | None = None,
    ) -> None:
        """Inserta o actualiza un usuario (sin tocar el nickname si ya existe)."""
        query = """
            INSERT INTO users (
                user_id, username, display_name,
                is_moderator, is_vip, is_subscriber
            )
            VALUES (?, ?, ?, COALESCE(?, 0), COALESCE(?, 0), COALESCE(?, 0))
            ON CONFLICT(user_id)
            DO UPDATE SET username      = excluded.username,
                          display_name  = excluded.display_name,
                          is_moderator  = COALESCE(?, users.is_moderator),
                          is_vip        = COALESCE(?, users.is_vip),
                          is_subscriber = COALESCE(?, users.is_subscriber);
        """
        mod_val = int(is_moderator) if is_moderator is not None else None
        vip_val = int(is_vip) if is_vip is not None else None
        sub_val = int(is_subscriber) if is_subscriber is not None else None

        async with self._db.acquire() as conn:
            await conn.execute(
                query,
                (
                    user_id,
                    username,
                    display_name,
                    mod_val,
                    vip_val,
                    sub_val,
                    mod_val,
                    vip_val,
                    sub_val,
                ),
            )

    async def get_user_nickname(self, user_id: str) -> str | None:
        """Devuelve el nickname del usuario, o None si no tiene."""
        async with self._db.acquire() as conn:
            row: sqlite3.Row | None = await conn.fetchone(
                "SELECT nickname FROM users WHERE user_id = ?", (user_id,)
            )
        return row["nickname"] if row else None

    async def get_user_id_by_name(self, username: str) -> str | None:
        """Devuelve el user_id de un usuario a partir de su username."""
        async with self._db.acquire() as conn:
            row: sqlite3.Row | None = await conn.fetchone(
                "SELECT user_id FROM users WHERE username = ? COLLATE NOCASE",
                (username,),
            )
        return row["user_id"] if row else None

    async def set_nickname(self, user_id: str, nickname: str | None) -> None:
        """Establece o elimina el apodo personalizado de un usuario."""
        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET nickname = ? WHERE user_id = ?",
                (nickname, user_id),
            )

    async def is_user_bot(self, user_id: str) -> bool:
        """Devuelve True si el usuario está marcado como bot en la DB."""
        async with self._db.acquire() as conn:
            row: sqlite3.Row | None = await conn.fetchone(
                "SELECT is_bot FROM users WHERE user_id = ?", (user_id,)
            )
        return bool(row["is_bot"]) if row else False

    async def set_user_bot(self, user_id: str, is_bot: bool) -> None:
        """Marca o desmarca un usuario como bot."""
        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_bot = ? WHERE user_id = ?",
                (1 if is_bot else 0, user_id),
            )

    async def get_users_info(
        self, user_ids: list[str]
    ) -> dict[str, dict[str, str | None]]:
        """Devuelve info de visualización para los IDs de usuario dados."""
        if not user_ids:
            return {}
        placeholders = ", ".join("?" * len(user_ids))
        query = (
            "SELECT user_id, display_name, nickname FROM users"
            f" WHERE user_id IN ({placeholders})"
        )
        async with self._db.acquire() as conn:
            rows: list[sqlite3.Row] = await conn.fetchall(query, tuple(user_ids))
        return {
            row["user_id"]: {
                "display_name": row["display_name"],
                "nickname": row["nickname"],
            }
            for row in rows
        }

    async def get_unfollowers_data(
        self, channel_id: str, user_ids: list[str]
    ) -> dict[str, dict[str, str | None]]:
        """Devuelve info completa para usuarios que dejaron de seguir."""
        if not user_ids:
            return {}
        placeholders = ", ".join("?" * len(user_ids))
        query = (
            "SELECT u.user_id, u.display_name, u.nickname, f.followed_at"
            " FROM users u JOIN followers f ON u.user_id = f.user_id"
            f" WHERE f.channel_id = ? AND f.user_id IN ({placeholders})"
        )
        async with self._db.acquire() as conn:
            rows: list[sqlite3.Row] = await conn.fetchall(
                query, (channel_id, *user_ids)
            )
        return {
            row["user_id"]: {
                "display_name": row["display_name"],
                "nickname": row["nickname"],
                "followed_at": row["followed_at"],
            }
            for row in rows
        }

    async def get_user_roles(self, user_id: str) -> dict[str, bool] | None:
        """Devuelve los roles (moderador, VIP, suscriptor) del usuario."""
        query = """
            SELECT is_moderator, is_vip, is_subscriber
            FROM users
            WHERE user_id = ?
        """
        async with self._db.acquire() as conn:
            row: sqlite3.Row | None = await conn.fetchone(query, (user_id,))
        if not row:
            return None
        return {
            "is_moderator": bool(row["is_moderator"]),
            "is_vip": bool(row["is_vip"]),
            "is_subscriber": bool(row["is_subscriber"]),
        }

    async def get_user_detail_by_name(
        self, username: str, channel_id: str
    ) -> dict[str, Any] | None:
        """Obtiene información de roles y seguimiento de un usuario."""
        query = """
            SELECT u.username, u.display_name, u.nickname, u.is_bot,
                   u.is_moderator, u.is_vip, u.is_subscriber,
                   f.followed_at, f.unfollowed_at
            FROM users u
            LEFT JOIN followers f ON u.user_id = f.user_id AND f.channel_id = ?
            WHERE u.username = ? COLLATE NOCASE
        """
        async with self._db.acquire() as conn:
            row: sqlite3.Row | None = await conn.fetchone(query, (channel_id, username))
        if not row:
            return None
        return dict(row)

    async def list_users_with_filters(
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
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Devuelve usuarios registrados filtrados y el total coincidente."""
        limit = max(1, limit)
        offset = max(0, offset)
        where_clauses = []
        params: list[Any] = [channel_id]

        if role:
            role_clean = role.lower()
            if role_clean in ("bot", "bots"):
                where_clauses.append("u.is_bot = 1")
            elif role_clean in ("moderator", "moderador", "mods", "mod"):
                where_clauses.append("u.is_moderator = 1")
            elif role_clean in ("vip", "vips"):
                where_clauses.append("u.is_vip = 1")
            elif role_clean in (
                "subscriber",
                "suscriptor",
                "subscribers",
                "sub",
                "subs",
            ):
                where_clauses.append("u.is_subscriber = 1")

        if has_nickname is not None:
            if has_nickname:
                where_clauses.append("u.nickname IS NOT NULL AND u.nickname != ''")
            else:
                where_clauses.append("(u.nickname IS NULL OR u.nickname = '')")

        if username_search:
            where_clauses.append(
                "(u.username LIKE ? OR u.display_name LIKE ? OR u.nickname LIKE ?)"
            )
            like_pattern = f"%{username_search}%"
            params.extend([like_pattern, like_pattern, like_pattern])

        if followed_after:
            where_clauses.append("f.followed_at >= ?")
            params.append(followed_after)

        if followed_before:
            where_clauses.append("f.followed_at <= ?")
            params.append(followed_before)

        if unfollowed_after:
            where_clauses.append("f.unfollowed_at >= ?")
            params.append(unfollowed_after)

        if unfollowed_before:
            where_clauses.append("f.unfollowed_at <= ?")
            params.append(unfollowed_before)

        if is_follower and is_follower in ("follower", "not_follower", "unfollower"):
            if broadcaster_id:
                where_clauses.append("u.user_id != ?")
                params.append(broadcaster_id)

            if is_follower == "follower":
                where_clauses.append(
                    "f.followed_at IS NOT NULL AND f.unfollowed_at IS NULL"
                )
            elif is_follower == "not_follower":
                where_clauses.append("f.user_id IS NULL")
            elif is_follower == "unfollower":
                where_clauses.append("f.unfollowed_at IS NOT NULL")

        count_query = """
            SELECT COUNT(*) AS total
            FROM users u
            LEFT JOIN followers f ON u.user_id = f.user_id AND f.channel_id = ?
        """
        if where_clauses:
            count_query += " WHERE " + " AND ".join(where_clauses)

        query = """
            SELECT u.user_id, u.username, u.display_name, u.nickname, u.is_bot,
                   u.is_moderator, u.is_vip, u.is_subscriber,
                   f.followed_at, f.unfollowed_at
            FROM users u
            LEFT JOIN followers f ON u.user_id = f.user_id AND f.channel_id = ?
        """
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY u.username ASC LIMIT ? OFFSET ?"

        count_params = params.copy()
        data_params = params.copy()
        data_params.extend([limit, offset])

        async with self._db.acquire() as conn:
            count_row = await conn.fetchone(count_query, tuple(count_params))
            total_count = count_row["total"] if count_row else 0

            rows: list[sqlite3.Row] = await conn.fetchall(query, tuple(data_params))

        return [dict(row) for row in rows], total_count

    async def update_user_roles(
        self,
        user_id: str,
        is_bot: bool,
        is_moderator: bool,
        is_vip: bool,
    ) -> None:
        """Actualiza los roles de un usuario en la base de datos."""
        query = """
            UPDATE users
            SET is_bot = ?,
                is_moderator = ?,
                is_vip = ?
            WHERE user_id = ?
        """
        async with self._db.acquire() as conn:
            await conn.execute(
                query,
                (
                    int(is_bot),
                    int(is_moderator),
                    int(is_vip),
                    user_id,
                ),
            )

    async def search_users(self, q: str, limit: int = 10) -> list[dict[str, Any]]:
        """Busca usuarios en la DB local para autocompletar."""
        query = """
            SELECT u.user_id, u.username, u.display_name,
                   COALESCE(u.nickname, '') AS nickname,
                   u.is_bot, u.is_moderator, u.is_vip, u.is_subscriber,
                   (f.user_id IS NOT NULL AND f.unfollowed_at IS NULL) AS is_follower
            FROM users u
            LEFT JOIN followers f ON u.user_id = f.user_id
            WHERE u.username LIKE ? OR u.display_name LIKE ? OR u.nickname LIKE ?
            GROUP BY u.user_id
            ORDER BY u.display_name
            LIMIT ?
        """
        async with self._db.acquire() as conn:
            rows: list[sqlite3.Row] = await conn.fetchall(
                query, (f"%{q}%", f"%{q}%", f"%{q}%", limit)
            )
        return [dict(row) for row in rows]
