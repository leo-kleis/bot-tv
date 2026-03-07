from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import asqlite
from twitchio import eventsub

from bot_tv.env import BOT_ID

# src/bot_tv/database.py -> src/bot_tv -> src -> src/db
DB_DIR = Path(__file__).resolve().parent.parent / "db"
DB_PATH = DB_DIR / "tokens.db"

if TYPE_CHECKING:
    import sqlite3


async def setup_database(
    db: asqlite.Pool,
) -> tuple[list[tuple[str, str]], list[eventsub.SubscriptionPayload]]:
    """Crea las tablas necesarias y carga los tokens existentes."""
    query = """CREATE TABLE IF NOT EXISTS tokens(
        user_id TEXT PRIMARY KEY,
        token   TEXT NOT NULL,
        refresh TEXT NOT NULL
    )"""
    async with db.acquire() as connection:
        await connection.execute(query)
        rows: list[sqlite3.Row] = await connection.fetchall("SELECT * FROM tokens")

    tokens: list[tuple[str, str]] = []
    subs: list[eventsub.SubscriptionPayload] = []
    for row in rows:
        tokens.append((row["token"], row["refresh"]))
        if row["user_id"] != BOT_ID:
            subs.append(
                eventsub.ChatMessageSubscription(
                    broadcaster_user_id=row["user_id"], user_id=BOT_ID
                )
            )
    return tokens, subs


async def save_token(db: asqlite.Pool, user_id: str, token: str, refresh: str) -> None:
    """Inserta o actualiza un token en la base de datos."""
    query = """
        INSERT INTO tokens (user_id, token, refresh)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET token = excluded.token, refresh = excluded.refresh;
    """
    async with db.acquire() as connection:
        await connection.execute(query, (user_id, token, refresh))
