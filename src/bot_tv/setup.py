"""Script interactivo de configuración y autorización OAuth mediante
Device Code Flow (DCF).
"""

from __future__ import annotations

import asyncio
import logging
import sys

import twitchio

from bot_tv.database import (
    TokenRepository,
    create_pg_pool,
)
from bot_tv.utils.env import BOT_ID, CLIENT_ID, OWNER_ID
from bot_tv.utils.logger import setup_logging

LOGGER = logging.getLogger(__name__)

# ── Scopes para la cuenta BOT ──────────────────────────────────────
# Permisos que el bot necesita para actuar (user:*, chat:*, moderator:*)
BOT_SCOPES: list[str] = [
    # Chat y bot
    "user:read:chat",
    "user:write:chat",
    "user:bot",
    "chat:read",
    "chat:edit",
    # Broadcast (usuario)
    "user:read:broadcast",
    "user:edit:broadcast",
    # Moderación (el bot actúa como moderador)
    "moderation:read",
    "moderator:manage:announcements",
    "moderator:read:chat_settings",
    "moderator:manage:chat_settings",
    "moderator:read:chatters",
    "moderator:read:moderators",
    "moderator:manage:moderators",
    "moderator:read:shield_mode",
    "moderator:manage:shield_mode",
    "moderator:read:guest_star",
    "moderator:manage:guest_star",
    # Clips
    "clips:edit",
    # Otros
    "user:read:email",
    # Gestión de bans y mensajes del chat
    "moderator:manage:banned_users",
    "moderator:manage:chat_messages",
]

# ── Scopes para la cuenta CANAL ─────────────────────────────────────
# Permisos que el dueño del canal concede (channel:*, analytics:*, bits:*)
CHANNEL_SCOPES: list[str] = [
    # Chat y bot
    "channel:bot",
    "user:read:chat",
    "user:write:chat",
    "channel:moderate",
    # Moderación (el dueño concede permisos de moderación)
    "moderator:manage:banned_users",
    "moderator:manage:chat_messages",
    # Anuncios y ads
    "channel:manage:ads",
    "channel:read:ads",
    # Broadcast (canal)
    "channel:manage:broadcast",
    # Predicciones y encuestas
    "channel:read:predictions",
    "channel:manage:predictions",
    "channel:read:polls",
    "channel:manage:polls",
    # Redenciones y recompensas
    "channel:read:redemptions",
    "channel:manage:redemptions",
    # Suscripciones
    "channel:read:subscriptions",
    # VIPs
    "channel:read:vips",
    "channel:manage:vips",
    # Moderadores
    "channel:read:moderators",
    "channel:manage:moderators",
    # Videos y clips
    "channel:manage:videos",
    # Programación
    "channel:manage:schedule",
    # Extensiones
    "channel:manage:extensions",
    # Analíticas
    "analytics:read:extensions",
    "analytics:read:games",
    "bits:read",
    # Otros
    "channel:read:charity",
    "channel:edit:commercial",
    "channel:read:editors",
    "channel:read:goals",
    "channel:read:guest_star",
    "channel:manage:guest_star",
    "channel:read:hype_train",
    "channel:read:stream_key",
    # Seguidores
    "moderator:read:followers",
    # Clips
    "clips:edit",
]


class DCFClient(twitchio.Client):
    """Cliente mínimo para autorizar una cuenta vía Device Code Flow."""

    def __init__(self, *, client_id: str) -> None:
        self.authorized_payload: twitchio.authentication.ValidateTokenPayload | None = (
            None
        )
        self.token_pair: tuple[str, str] | None = None
        super().__init__(client_id=client_id)

    async def add_token(
        self, token: str, refresh: str
    ) -> twitchio.authentication.ValidateTokenPayload:
        validated = await super().add_token(token, refresh)
        self.authorized_payload = validated
        self.token_pair = (token, refresh)
        return validated


async def authorize_account(
    *,
    client_id: str,
    scopes_list: list[str],
    step_title: str,
    account_label: str,
    expected_id: str,
    token_repo: TokenRepository,
) -> None:
    """Ejecuta el flujo DCF para autorizar una cuenta y persistirla en la DB."""
    client = DCFClient(client_id=client_id)
    scopes = twitchio.Scopes(scopes_list)

    LOGGER.info("=" * 65)
    LOGGER.info("%s (%d scopes)", step_title, len(scopes_list))
    LOGGER.info("Solicitando código de autorización a Twitch...")

    dcf_resp = await client.login_dcf(
        load_token=False,
        save_token=False,
        scopes=scopes,
        force_flow=True,
    )
    if not dcf_resp:
        raise RuntimeError(f"No se pudo iniciar el flujo DCF para {account_label}")

    uri = dcf_resp.get("verification_uri", "https://www.twitch.tv/activate")
    code = dcf_resp["user_code"]
    expires_in = dcf_resp.get("expires_in", 1800)
    interval = dcf_resp.get("interval", 5)

    LOGGER.info("")
    LOGGER.info("  1. Abre este enlace en tu navegador (PC o celular):")
    LOGGER.info("     %s", uri)
    LOGGER.info("")
    LOGGER.info(
        "  2. Inicia sesión en Twitch con la cuenta de: %s.",
        account_label.upper(),
    )
    LOGGER.info(
        "  3. Si el campo no se autocompleta, ingresa el código: %s",
        code,
    )
    LOGGER.info("     (El código expira en %d minutos)", expires_in // 60)
    LOGGER.info("")
    LOGGER.info("Esperando que autorices la cuenta en Twitch...")

    try:
        await client.start_dcf(
            device_code=dcf_resp["device_code"],
            interval=interval,
            timeout=expires_in,
            scopes=scopes,
            block=False,
        )
    finally:
        await client.close()

    if not client.authorized_payload or not client.token_pair:
        raise RuntimeError(
            f"No se recibieron credenciales para la cuenta {account_label}."
        )

    user_id = client.authorized_payload.user_id or ""
    username = client.authorized_payload.login or ""
    access_token, refresh_token = client.token_pair

    if expected_id and user_id != expected_id:
        LOGGER.warning(
            "Aviso: El ID obtenido (%s) no coincide con el configurado en .env (%s).",
            user_id,
            expected_id,
        )

    LOGGER.info(
        "[OK] Cuenta %s autorizada: %s (ID: %s)",
        account_label,
        username,
        user_id,
    )

    await token_repo.save_token(
        user_id=user_id,
        username=username,
        token=access_token,
        refresh=refresh_token,
    )
    LOGGER.info("[OK] Tokens encriptados y guardados en PostgreSQL.")
    LOGGER.info("")


def setup() -> None:
    """Punto de entrada del script de configuración."""
    setup_logging(level=logging.INFO)

    if not CLIENT_ID:
        LOGGER.critical(
            "Falta la variable TWITCH_CLIENT_ID en el archivo .env. "
            "Configúrala antes de ejecutar el setup."
        )
        sys.exit(1)

    async def runner() -> None:
        LOGGER.info("=" * 65)
        LOGGER.info("SETUP: Autorización OAuth con Device Code Flow (DCF)")
        LOGGER.info("=" * 65)
        LOGGER.info("Conectando a PostgreSQL...")

        pool = await create_pg_pool(direct=True)
        try:
            token_repo = TokenRepository(pool)

            # Paso 1: Cuenta BOT
            await authorize_account(
                client_id=CLIENT_ID,
                scopes_list=BOT_SCOPES,
                step_title="PASO 1 DE 2: Autorizar cuenta BOT",
                account_label="Bot",
                expected_id=BOT_ID,
                token_repo=token_repo,
            )

            # Paso 2: Cuenta CANAL
            await authorize_account(
                client_id=CLIENT_ID,
                scopes_list=CHANNEL_SCOPES,
                step_title="PASO 2 DE 2: Autorizar cuenta CANAL",
                account_label="Canal / Streamer",
                expected_id=OWNER_ID,
                token_repo=token_repo,
            )

            LOGGER.info("=" * 65)
            LOGGER.info("Configuración completada con éxito.")
            LOGGER.info(
                "Ambas cuentas han sido autorizadas y almacenadas en la base de datos."
            )
            LOGGER.info("Ya puedes iniciar el bot con: bot-web")
            LOGGER.info("=" * 65)
        finally:
            await pool.close()

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOGGER.info("Setup cancelado por el usuario.")
    except Exception as exc:
        LOGGER.critical("Error durante el setup: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    setup()
