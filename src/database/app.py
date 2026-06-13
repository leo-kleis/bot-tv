from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import asqlite

from database.tokens import DB_DIR

if TYPE_CHECKING:
    import sqlite3

# Base de datos de la aplicación (separada de tokens.db)
APP_DB_PATH = DB_DIR / "app.db"


async def setup_app_database(db: asqlite.Pool) -> None:
    """Crea las tablas de la aplicación si no existen."""
    async with db.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id      TEXT PRIMARY KEY,
                username     TEXT NOT NULL,
                display_name TEXT,
                nickname     TEXT,
                is_bot       INTEGER DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                user_id    TEXT NOT NULL,
                message    TEXT NOT NULL,
                timestamp  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS followers (
                channel_id  TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                followed_at TEXT,
                unfollowed_at TEXT,
                PRIMARY KEY (channel_id, user_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Migración: agregar columna is_bot si la DB ya existía sin ella
        with contextlib.suppress(Exception):
            await conn.execute("ALTER TABLE users ADD COLUMN is_bot INTEGER DEFAULT 0")

        # Migración: agregar columna unfollowed_at a followers
        with contextlib.suppress(Exception):
            await conn.execute("ALTER TABLE followers ADD COLUMN unfollowed_at TEXT")


async def upsert_user(
    db: asqlite.Pool,
    user_id: str,
    username: str,
    display_name: str | None = None,
) -> None:
    """Inserta o actualiza un usuario (sin tocar el nickname si ya existe)."""
    query = """
        INSERT INTO users (user_id, username, display_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET username     = excluded.username,
                      display_name = excluded.display_name;
    """
    async with db.acquire() as conn:
        await conn.execute(query, (user_id, username, display_name))


async def get_user_nickname(db: asqlite.Pool, user_id: str) -> str | None:
    """Devuelve el nickname del usuario, o None si no tiene."""
    async with db.acquire() as conn:
        row: sqlite3.Row | None = await conn.fetchone(
            "SELECT nickname FROM users WHERE user_id = ?", (user_id,)
        )
    return row["nickname"] if row else None


async def get_user_id_by_name(db: asqlite.Pool, username: str) -> str | None:
    """Devuelve el user_id de un usuario a partir de su username,
    o None si no existe."""
    async with db.acquire() as conn:
        row: sqlite3.Row | None = await conn.fetchone(
            "SELECT user_id FROM users WHERE username = ?", (username,)
        )
    return row["user_id"] if row else None


async def set_nickname(db: asqlite.Pool, user_id: str, nickname: str | None) -> None:
    """Establece o elimina el apodo personalizado de un usuario."""
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE users SET nickname = ? WHERE user_id = ?",
            (nickname, user_id),
        )


async def is_user_bot(db: asqlite.Pool, user_id: str) -> bool:
    """Devuelve True si el usuario está marcado como bot en la DB."""
    async with db.acquire() as conn:
        row: sqlite3.Row | None = await conn.fetchone(
            "SELECT is_bot FROM users WHERE user_id = ?", (user_id,)
        )
    return bool(row["is_bot"]) if row else False


async def set_user_bot(db: asqlite.Pool, user_id: str, is_bot: bool) -> None:
    """Marca o desmarca un usuario como bot."""
    async with db.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_bot = ? WHERE user_id = ?",
            (1 if is_bot else 0, user_id),
        )


async def save_chat_message(
    db: asqlite.Pool,
    channel_id: str,
    user_id: str,
    message: str,
) -> None:
    """Guarda un mensaje en el historial de chat."""
    now = datetime.now(UTC).isoformat()
    query = """
        INSERT INTO chat_history (channel_id, user_id, message, timestamp)
        VALUES (?, ?, ?, ?)
    """
    async with db.acquire() as conn:
        await conn.execute(query, (channel_id, user_id, message, now))


async def get_follower_ids(db: asqlite.Pool, channel_id: str) -> set[str]:
    """Devuelve el conjunto de user_id que siguen a un canal."""
    async with db.acquire() as conn:
        rows: list[sqlite3.Row] = await conn.fetchall(
            "SELECT user_id FROM followers "
            "WHERE channel_id = ? AND unfollowed_at IS NULL",
            (channel_id,),
        )
    return {row["user_id"] for row in rows}


async def get_users_info(
    db: asqlite.Pool, user_ids: list[str]
) -> dict[str, dict[str, str | None]]:
    """Devuelve {user_id: {"display_name": ..., "nickname": ...}} para los IDs dados."""
    if not user_ids:
        return {}
    placeholders = ", ".join("?" * len(user_ids))
    query = (
        "SELECT user_id, display_name, nickname FROM users"
        f" WHERE user_id IN ({placeholders})"
    )
    async with db.acquire() as conn:
        rows: list[sqlite3.Row] = await conn.fetchall(query, tuple(user_ids))
    return {
        row["user_id"]: {
            "display_name": row["display_name"],
            "nickname": row["nickname"],
        }
        for row in rows
    }


async def get_unfollowers_data(
    db: asqlite.Pool, channel_id: str, user_ids: list[str]
) -> dict[str, dict[str, str | None]]:
    """Devuelve info completa para usuarios que dejaron de seguir.

    Combina users (display_name, nickname) con followers (followed_at).
    Retorna {user_id: {"display_name": ..., "nickname": ..., "followed_at": ...}}
    """
    if not user_ids:
        return {}
    placeholders = ", ".join("?" * len(user_ids))
    query = (
        "SELECT u.user_id, u.display_name, u.nickname, f.followed_at"
        " FROM users u JOIN followers f ON u.user_id = f.user_id"
        f" WHERE f.channel_id = ? AND f.user_id IN ({placeholders})"
    )
    async with db.acquire() as conn:
        rows: list[sqlite3.Row] = await conn.fetchall(query, (channel_id, *user_ids))
    return {
        row["user_id"]: {
            "display_name": row["display_name"],
            "nickname": row["nickname"],
            "followed_at": row["followed_at"],
        }
        for row in rows
    }


async def sync_followers(
    db: asqlite.Pool,
    channel_id: str,
    followers: list[tuple[str, str, str | None]],
    unfollowed_ids: list[str] | None = None,
) -> None:
    """Actualiza los servidores de un canal marcando los que dejaron de seguir.

    Args:
        db: Pool de la base de datos.
        channel_id: ID del canal.
        followers: Lista de tuplas (user_id, username, followed_at).
        unfollowed_ids: Lista de ID que dejaron de seguir.
    """
    if unfollowed_ids is None:
        unfollowed_ids = []

    now_iso = datetime.now(UTC).isoformat()

    async with db.acquire() as conn:
        # Marcar los que dejaron de seguir
        for uid in unfollowed_ids:
            await conn.execute(
                "UPDATE followers SET unfollowed_at = ? "
                "WHERE channel_id = ? AND user_id = ?",
                (now_iso, channel_id, uid),
            )

        # Insertar o actualizar los seguidores actuales
        for user_id, username, followed_at in followers:
            # Asegurar que el usuario existe en la tabla users
            await conn.execute(
                """
                INSERT INTO users (user_id, username)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
                WHERE users.username IS NOT excluded.username
                """,
                (user_id, username),
            )
            await conn.execute(
                """
                INSERT INTO followers (channel_id, user_id, followed_at, unfollowed_at)
                VALUES (?, ?, ?, NULL)
                ON CONFLICT(channel_id, user_id) DO UPDATE SET 
                    followed_at = excluded.followed_at,
                    unfollowed_at = NULL
                WHERE
                    followers.followed_at IS NOT excluded.followed_at OR
                    followers.unfollowed_at IS NOT NULL
                """,
                (channel_id, user_id, followed_at),
            )
