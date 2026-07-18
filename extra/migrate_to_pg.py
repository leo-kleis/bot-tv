"""Script one-time para migrar datos de SQLite (app.db + tokens.db) a PostgreSQL.

Uso:
    uv run python extra/migrate_to_pg.py

Requiere:
    - DATABASE_URL y DIRECT_URL configurados en .env
    - db/app.db y db/tokens.db existentes con datos
    - asyncpg y aiosqlite instalados
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()

from bot_tv.database.migrations import run_pg_migrations  # noqa: E402

from bot_tv.database.connection import create_pg_pool  # noqa: E402
from bot_tv.utils.env import DIRECT_URL  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger(__name__)

APP_DB_PATH = Path("db/app.db")
TOKEN_DB_PATH = Path("db/tokens.db")


def read_sqlite(path: Path, query: str) -> list[sqlite3.Row]:
    """Lee datos de una base de datos SQLite de forma síncrona."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows


async def migrate_users(pg: asyncpg.Connection, rows: list[sqlite3.Row]) -> int:
    count = 0
    for row in rows:
        await pg.execute(
            """
            INSERT INTO users (
                user_id, username, display_name, nickname,
                is_bot, is_moderator, is_vip, is_subscriber, profile_image_url
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (user_id) DO NOTHING
            """,
            row["user_id"],
            row["username"],
            row["display_name"],
            row["nickname"],
            bool(row["is_bot"]),
            bool(row["is_moderator"]),
            bool(row["is_vip"]),
            bool(row["is_subscriber"]),
            row["profile_image_url"],
        )
        count += 1
    return count


async def migrate_chat_history(pg: asyncpg.Connection, rows: list[sqlite3.Row]) -> int:
    count = 0
    for row in rows:
        await pg.execute(
            """
            INSERT INTO chat_history (channel_id, user_id, message, timestamp)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING
            """,
            row["channel_id"],
            row["user_id"],
            row["message"],
            row["timestamp"],
        )
        count += 1
    return count


async def migrate_followers(pg: asyncpg.Connection, rows: list[sqlite3.Row]) -> int:
    count = 0
    for row in rows:
        await pg.execute(
            """
            INSERT INTO followers (channel_id, user_id, followed_at, unfollowed_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (channel_id, user_id) DO NOTHING
            """,
            row["channel_id"],
            row["user_id"],
            row["followed_at"],
            row["unfollowed_at"],
        )
        count += 1
    return count


async def migrate_app_settings(pg: asyncpg.Connection, rows: list[sqlite3.Row]) -> int:
    count = 0
    for row in rows:
        await pg.execute(
            """
            INSERT INTO app_settings (key, value)
            VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            row["key"],
            row["value"],
        )
        count += 1
    return count


async def migrate_api_consumption_log(
    pg: asyncpg.Connection, rows: list[sqlite3.Row]
) -> int:
    count = 0
    for row in rows:
        await pg.execute(
            """
            INSERT INTO api_consumption_log (model, timestamp, type)
            VALUES ($1, $2, $3)
            """,
            row["model"],
            float(row["timestamp"]),
            row["type"],
        )
        count += 1
    return count


async def migrate_tokens(pg: asyncpg.Connection, rows: list[sqlite3.Row]) -> int:
    count = 0
    for row in rows:
        await pg.execute(
            """
            INSERT INTO tokens (user_id, username, token, refresh)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO NOTHING
            """,
            row["user_id"],
            row["username"],
            row["token"],
            row["refresh"],
        )
        count += 1
    return count


async def main() -> None:
    if not APP_DB_PATH.exists():
        LOGGER.error("No se encontró %s", APP_DB_PATH)
        return
    if not TOKEN_DB_PATH.exists():
        LOGGER.error("No se encontró %s", TOKEN_DB_PATH)
        return
    if not DIRECT_URL:
        LOGGER.error("DIRECT_URL no está configurado en .env")
        return

    LOGGER.info("Leyendo datos de SQLite...")
    users = read_sqlite(APP_DB_PATH, "SELECT * FROM users")
    chat = read_sqlite(APP_DB_PATH, "SELECT * FROM chat_history")
    followers = read_sqlite(APP_DB_PATH, "SELECT * FROM followers")
    settings = read_sqlite(APP_DB_PATH, "SELECT * FROM app_settings")
    api_log = read_sqlite(APP_DB_PATH, "SELECT * FROM api_consumption_log")
    tokens = read_sqlite(TOKEN_DB_PATH, "SELECT * FROM tokens")

    LOGGER.info(
        "Registros encontrados: users=%d, chat=%d, followers=%d, "
        "settings=%d, api_log=%d, tokens=%d",
        len(users),
        len(chat),
        len(followers),
        len(settings),
        len(api_log),
        len(tokens),
    )

    LOGGER.info("Conectando a PostgreSQL...")
    pool = await create_pg_pool(direct=True)
    try:
        await run_pg_migrations(pool)

        async with pool.acquire() as conn, conn.transaction():
            n_users = await migrate_users(conn, users)
            LOGGER.info("users migrados: %d", n_users)

            n_tokens = await migrate_tokens(conn, tokens)
            LOGGER.info("tokens migrados: %d", n_tokens)

            n_chat = await migrate_chat_history(conn, chat)
            LOGGER.info("chat_history migrados: %d", n_chat)

            n_followers = await migrate_followers(conn, followers)
            LOGGER.info("followers migrados: %d", n_followers)

            n_settings = await migrate_app_settings(conn, settings)
            LOGGER.info("app_settings migrados: %d", n_settings)

            n_api_log = await migrate_api_consumption_log(conn, api_log)
            LOGGER.info("api_consumption_log migrados: %d", n_api_log)

        LOGGER.info("Migración completada exitosamente.")
        LOGGER.info(
            "Los archivos SQLite (db/app.db, db/tokens.db) NO fueron eliminados. "
            "Puedes borrarlos manualmente cuando confirmes que todo funciona."
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
