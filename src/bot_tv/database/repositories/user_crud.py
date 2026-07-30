from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import asyncpg

from bot_tv.database.repositories.base import BaseRepository

if TYPE_CHECKING:
    from bot_tv.database.user_cache import UserMemoryCache

LOGGER = logging.getLogger(__name__)


class UserCrudMixin(BaseRepository):
    """Métodos CRUD principales para la entidad usuario."""

    async def upsert_user(
        self,
        user_id: str,
        username: str,
        display_name: str | None = None,
        cache: UserMemoryCache | None = None,
    ) -> None:
        """Inserta o actualiza un usuario (sin tocar el nickname si ya existe)."""
        if cache is not None:
            if not cache.needs_user_update(user_id, username, display_name):
                return
            cache.update_user(user_id, username, display_name)

        LOGGER.info(
            "DB UPDATE/INSERT usuario en PostgreSQL: %s (ID: %s)", username, user_id
        )
        query = """
            INSERT INTO users (user_id, username, display_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id)
            DO UPDATE SET username      = EXCLUDED.username,
                          display_name  = EXCLUDED.display_name
        """
        async with self._db.acquire() as conn:
            await conn.execute(
                query,
                user_id,
                username,
                display_name,
            )

    async def get_user_nickname(
        self, user_id: str, cache: UserMemoryCache | None = None
    ) -> str | None:
        """Devuelve el nickname del usuario, o None si no tiene."""
        if cache is not None:
            return cache.get_user_nickname(user_id)
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                "SELECT nickname FROM users WHERE user_id = $1", user_id
            )
        return row["nickname"] if row else None

    async def get_user_id_by_name(
        self, username: str, cache: UserMemoryCache | None = None
    ) -> str | None:
        """Devuelve el user_id de un usuario a partir de su username."""
        if cache is not None:
            cached_id = cache.get_user_id_by_name(username)
            if cached_id is not None:
                return cached_id
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                "SELECT user_id FROM users WHERE username ILIKE $1",
                username,
            )
        return row["user_id"] if row else None

    async def set_nickname(
        self, user_id: str, nickname: str | None, cache: UserMemoryCache | None = None
    ) -> None:
        """Establece o elimina el apodo personalizado de un usuario."""
        if cache is not None:
            cache.set_nickname(user_id, nickname)
        LOGGER.info("DB UPDATE apodo para user_id %s: %s", user_id, nickname)
        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET nickname = $1 WHERE user_id = $2",
                nickname,
                user_id,
            )

    async def is_user_bot(
        self, user_id: str, cache: UserMemoryCache | None = None
    ) -> bool:
        """Devuelve True si el usuario está marcado como bot en la DB."""
        if cache is not None:
            return cache.is_user_bot(user_id)
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                "SELECT is_bot FROM users WHERE user_id = $1", user_id
            )
        return bool(row["is_bot"]) if row else False

    async def set_user_bot(
        self, user_id: str, is_bot: bool, cache: UserMemoryCache | None = None
    ) -> None:
        """Marca o desmarca un usuario como bot."""
        if cache is not None:
            cache.set_user_bot(user_id, is_bot)
        LOGGER.info("DB UPDATE bot status para user_id %s: %s", user_id, is_bot)
        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_bot = $1 WHERE user_id = $2",
                is_bot,
                user_id,
            )

    async def get_users_info(
        self, user_ids: list[str]
    ) -> dict[str, dict[str, str | None]]:
        """Devuelve info de visualización para los IDs de usuario dados."""
        if not user_ids:
            return {}
        query = (
            "SELECT user_id, display_name, nickname FROM users WHERE user_id = ANY($1)"
        )
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch(query, user_ids)
        return {
            row["user_id"]: {
                "display_name": row["display_name"],
                "nickname": row["nickname"],
            }
            for row in rows
        }

    async def get_profile_image_url(
        self, user_id: str, cache: UserMemoryCache | None = None
    ) -> str | None:
        """Devuelve la URL del avatar cacheada, o None si no existe."""
        if cache is not None:
            url = cache.get_profile_image_url(user_id)
            if url is not None:
                return url
        async with self._db.acquire() as conn:
            row: asyncpg.Record | None = await conn.fetchrow(
                "SELECT profile_image_url FROM users WHERE user_id = $1",
                user_id,
            )
        if not row:
            return None
        return row["profile_image_url"]

    async def set_profile_image_url(
        self, user_id: str, url: str, cache: UserMemoryCache | None = None
    ) -> None:
        """Guarda o actualiza la URL del avatar del usuario."""
        if cache is not None:
            cache.set_profile_image_url(user_id, url)
        LOGGER.debug("DB UPDATE avatar para user_id %s en PostgreSQL", user_id)

        async with self._db.acquire() as conn:
            await conn.execute(
                "UPDATE users SET profile_image_url = $1 WHERE user_id = $2",
                url,
                user_id,
            )
