from __future__ import annotations

import base64
import hashlib
import logging

import asyncpg
from cryptography.fernet import Fernet, InvalidToken

from bot_tv.utils.env import CLIENT_SECRET

LOGGER = logging.getLogger(__name__)


def get_fernet() -> Fernet:
    """Deriva una clave Fernet determinista de 32 bytes a partir del CLIENT_SECRET."""
    key = base64.urlsafe_b64encode(hashlib.sha256(CLIENT_SECRET.encode()).digest())
    return Fernet(key)


async def run_pg_migrations(pool: asyncpg.Pool) -> None:
    """Crea todas las tablas e índices en PostgreSQL si no existen.

    Combina las migraciones de app.db y tokens.db en un único schema.
    """
    async with pool.acquire() as conn:
        # ── Tablas de la app ──────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id           TEXT PRIMARY KEY,
                username          TEXT NOT NULL,
                display_name      TEXT,
                nickname          TEXT,
                is_bot            BOOLEAN DEFAULT FALSE,
                is_moderator      BOOLEAN DEFAULT FALSE,
                is_vip            BOOLEAN DEFAULT FALSE,
                is_subscriber     BOOLEAN DEFAULT FALSE,
                profile_image_url TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                channel_id TEXT NOT NULL,
                user_id    TEXT NOT NULL REFERENCES users(user_id),
                message    TEXT NOT NULL,
                timestamp  TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS followers (
                channel_id    TEXT NOT NULL,
                user_id       TEXT NOT NULL REFERENCES users(user_id),
                followed_at   TEXT,
                unfollowed_at TEXT,
                PRIMARY KEY (channel_id, user_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_consumption_log (
                id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                model     TEXT NOT NULL,
                timestamp DOUBLE PRECISION NOT NULL,
                type      TEXT NOT NULL
            )
        """)

        # ── Tabla de tokens (antes en tokens.db) ─────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                user_id  TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                token    TEXT NOT NULL,
                refresh  TEXT NOT NULL
            )
        """)

        # ── Columnas opcionales (migraciones incrementales) ──────────
        # Agregar columnas que podrían faltar en DBs existentes
        for sql in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_bot BOOLEAN DEFAULT FALSE",
            (
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS"
                " is_moderator BOOLEAN DEFAULT FALSE"
            ),
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_vip BOOLEAN DEFAULT FALSE",
            (
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS"
                " is_subscriber BOOLEAN DEFAULT FALSE"
            ),
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_image_url TEXT",
            "ALTER TABLE followers ADD COLUMN IF NOT EXISTS unfollowed_at TEXT",
        ]:
            await conn.execute(sql)

        # ── Índices de rendimiento ────────────────────────────────────
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_history_user_id "
            "ON chat_history(user_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_history_channel_timestamp "
            "ON chat_history(channel_id, timestamp)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_followers_user_id ON followers(user_id)"
        )

    # Migrar tokens en texto plano a encriptados (si los hay)
    await _migrate_plaintext_tokens(pool)


async def _migrate_plaintext_tokens(pool: asyncpg.Pool) -> None:
    """Encripta tokens existentes que no estén encriptados."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, username, token, refresh FROM tokens")

    if not rows:
        return

    fernet = get_fernet()
    migrated_count = 0

    async with pool.acquire() as conn:
        for row in rows:
            user_id = row["user_id"]
            username = row["username"]
            raw_token = row["token"]
            raw_refresh = row["refresh"]

            token_needs_encrypt = False
            refresh_needs_encrypt = False

            try:
                fernet.decrypt(raw_token.encode())
            except InvalidToken:
                token_needs_encrypt = True

            try:
                fernet.decrypt(raw_refresh.encode())
            except InvalidToken:
                refresh_needs_encrypt = True

            if token_needs_encrypt or refresh_needs_encrypt:
                enc_token = raw_token
                enc_refresh = raw_refresh

                if token_needs_encrypt:
                    enc_token = fernet.encrypt(raw_token.encode()).decode()
                if refresh_needs_encrypt:
                    enc_refresh = fernet.encrypt(raw_refresh.encode()).decode()

                await conn.execute(
                    "UPDATE tokens SET token = $1, refresh = $2 WHERE user_id = $3",
                    enc_token,
                    enc_refresh,
                    user_id,
                )
                migrated_count += 1
                LOGGER.info(
                    "Token migrado (encriptado) para: %s (ID: %s)", username, user_id
                )

    if migrated_count > 0:
        LOGGER.info("Se migraron/encriptaron %d tokens existentes.", migrated_count)
