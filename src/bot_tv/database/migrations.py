from __future__ import annotations

import base64
import contextlib
import hashlib
import logging

import asqlite
from cryptography.fernet import Fernet, InvalidToken

from bot_tv.utils.env import CLIENT_SECRET

LOGGER = logging.getLogger(__name__)


def get_fernet() -> Fernet:
    """Deriva una clave Fernet determinista de 32 bytes a partir del CLIENT_SECRET."""
    key = base64.urlsafe_b64encode(hashlib.sha256(CLIENT_SECRET.encode()).digest())
    return Fernet(key)


async def run_app_migrations(db: asqlite.Pool) -> None:
    """Ejecuta la inicialización y migraciones de la base de datos app.db."""
    async with db.acquire() as conn:
        # 1. Crear tablas base si no existen
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       TEXT PRIMARY KEY,
                username      TEXT NOT NULL,
                display_name  TEXT,
                nickname      TEXT,
                is_bot        INTEGER DEFAULT 0,
                is_moderator  INTEGER DEFAULT 0,
                is_vip        INTEGER DEFAULT 0,
                is_subscriber INTEGER DEFAULT 0
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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_consumption_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                model     TEXT NOT NULL,
                timestamp REAL NOT NULL,
                type      TEXT NOT NULL
            )
        """)

        # 2. Agregar columnas faltantes en DBs existentes de forma incremental
        with contextlib.suppress(Exception):
            await conn.execute("ALTER TABLE users ADD COLUMN is_bot INTEGER DEFAULT 0")

        with contextlib.suppress(Exception):
            await conn.execute(
                "ALTER TABLE users ADD COLUMN is_moderator INTEGER DEFAULT 0"
            )

        with contextlib.suppress(Exception):
            await conn.execute("ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0")

        with contextlib.suppress(Exception):
            await conn.execute(
                "ALTER TABLE users ADD COLUMN is_subscriber INTEGER DEFAULT 0"
            )

        with contextlib.suppress(Exception):
            await conn.execute("ALTER TABLE followers ADD COLUMN unfollowed_at TEXT")

        # 3. Crear índices de rendimiento
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


async def run_token_migrations(db: asqlite.Pool) -> None:
    """Inicializa tokens.db y migra tokens en texto plano a encriptados."""
    async with db.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                user_id  TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                token    TEXT NOT NULL,
                refresh  TEXT NOT NULL
            )
        """)
        # Cargar todos los tokens existentes para verificar si están encriptados
        rows = await conn.fetchall(
            "SELECT user_id, username, token, refresh FROM tokens"
        )

    if not rows:
        return

    fernet = get_fernet()
    migrated_count = 0

    async with db.acquire() as conn:
        for row in rows:
            user_id = row["user_id"]
            username = row["username"]
            raw_token = row["token"]
            raw_refresh = row["refresh"]

            token_needs_encrypt = False
            refresh_needs_encrypt = False

            # Comprobar token
            try:
                fernet.decrypt(raw_token.encode())
            except InvalidToken:
                token_needs_encrypt = True

            # Comprobar refresh token
            try:
                fernet.decrypt(raw_refresh.encode())
            except InvalidToken:
                refresh_needs_encrypt = True

            # Si alguno necesita encriptación, encriptamos ambos para consistencia
            if token_needs_encrypt or refresh_needs_encrypt:
                enc_token = raw_token
                enc_refresh = raw_refresh

                if token_needs_encrypt:
                    enc_token = fernet.encrypt(raw_token.encode()).decode()
                if refresh_needs_encrypt:
                    enc_refresh = fernet.encrypt(raw_refresh.encode()).decode()

                await conn.execute(
                    "UPDATE tokens SET token = ?, refresh = ? WHERE user_id = ?",
                    (enc_token, enc_refresh, user_id),
                )
                migrated_count += 1
                LOGGER.info(
                    "Token migrado (encriptado) para: %s (ID: %s)", username, user_id
                )

    if migrated_count > 0:
        LOGGER.info("Se migraron/encriptaron %d tokens existentes.", migrated_count)
