from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import asqlite

from bot_tv.database import DB_DIR

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
                PRIMARY KEY (channel_id, user_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Migración: agregar columna is_bot si la DB ya existía sin ella
        with contextlib.suppress(Exception):
            await conn.execute("ALTER TABLE users ADD COLUMN is_bot INTEGER DEFAULT 0")


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
            "SELECT user_id FROM followers WHERE channel_id = ?",
            (channel_id,),
        )
    return {row["user_id"] for row in rows}


async def sync_followers(
    db: asqlite.Pool,
    channel_id: str,
    followers: list[tuple[str, str, str | None]],
) -> None:
    """Reemplaza los seguidores de un canal con los datos actuales.

    Args:
        db: Pool de la base de datos.
        channel_id: ID del canal.
        followers: Lista de tuplas (user_id, username, followed_at).
    """
    async with db.acquire() as conn:
        # Borrar seguidores anteriores de este canal
        await conn.execute("DELETE FROM followers WHERE channel_id = ?", (channel_id,))
        # Insertar los seguidores actuales
        for user_id, username, followed_at in followers:
            # Asegurar que el usuario existe en la tabla users
            await conn.execute(
                """
                INSERT INTO users (user_id, username)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
                """,
                (user_id, username),
            )
            await conn.execute(
                """
                INSERT INTO followers (channel_id, user_id, followed_at)
                VALUES (?, ?, ?)
                """,
                (channel_id, user_id, followed_at),
            )
