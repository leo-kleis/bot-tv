from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import asqlite
import twitchio
from twitchio import eventsub

from utils.env import BOT_ID

# Apunta a db/ en la raíz del proyecto (fuera de src/)
DB_DIR = Path(__file__).resolve().parent.parent.parent / "db"
DB_PATH = DB_DIR / "tokens.db"

if TYPE_CHECKING:
    import sqlite3

LOGGER = logging.getLogger(__name__)


async def setup_token_database(
    db: asqlite.Pool,
) -> tuple[list[tuple[str, str]], list[eventsub.SubscriptionPayload]]:
    """Crea las tablas necesarias y carga los tokens existentes."""
    query = """CREATE TABLE IF NOT EXISTS tokens(
        user_id  TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        token    TEXT NOT NULL,
        refresh  TEXT NOT NULL
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
            subs.append(
                eventsub.StreamOnlineSubscription(broadcaster_user_id=row["user_id"])
            )
            subs.append(
                eventsub.StreamOfflineSubscription(broadcaster_user_id=row["user_id"])
            )
    return tokens, subs


async def save_token(
    db: asqlite.Pool, user_id: str, username: str, token: str, refresh: str
) -> None:
    """Inserta o actualiza un token en la base de datos."""
    query = """
        INSERT INTO tokens (user_id, username, token, refresh)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET username = excluded.username,
                      token    = excluded.token,
                      refresh  = excluded.refresh;
    """
    async with db.acquire() as connection:
        await connection.execute(query, (user_id, username, token, refresh))


class TokenPersistMixin:
    """Mixin que persiste tokens en la base de datos al añadirlos.

    La clase que use este mixin DEBE tener un atributo `token_database`
    de tipo `asqlite.Pool` y heredar de una clase que tenga `add_token`.
    """

    token_database: asqlite.Pool

    async def add_token(
        self, token: str, refresh: str
    ) -> twitchio.authentication.ValidateTokenPayload:
        """Añade y persiste un token de acceso en la base de datos."""
        # pyrefly: ignore [missing-attribute]
        resp: twitchio.authentication.ValidateTokenPayload = await super().add_token(
            token, refresh
        )
        if resp.user_id and resp.login:
            await save_token(
                self.token_database, resp.user_id, resp.login, token, refresh
            )
            LOGGER.info("Token almacenado para: %s (ID: %s)", resp.login, resp.user_id)
        return resp
