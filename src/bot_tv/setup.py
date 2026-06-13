import asyncio
import logging

import asqlite
import twitchio
from twitchio.ext import commands

from bot_tv.database.tokens import (
    DB_PATH,
    TokenPersistMixin,
    setup_token_database,
)
from bot_tv.utils.env import BOT_ID, CLIENT_ID, CLIENT_SECRET, DB_DIR, OWNER_ID
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
    # Gestión de mensajes del chat (borrar mensajes)
    "moderator:manage:chat_messages",
]

# ── Scopes para la cuenta CANAL ─────────────────────────────────────
# Permisos que el dueño del canal concede (channel:*, analytics:*, bits:*)
CHANNEL_SCOPES: list[str] = [
    # Chat y bot
    "channel:bot",
    "user:read:chat",
    "channel:moderate",
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


class SetupBot(TokenPersistMixin, commands.AutoBot):
    """Cliente mínimo para autorizar cuentas y guardar tokens."""

    def __init__(self, *, token_database: asqlite.Pool) -> None:
        self.token_database = token_database
        # Rastrear qué cuentas fueron autorizadas durante esta sesión
        self._authorized: set[str] = set()

        super().__init__(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            bot_id=BOT_ID,
            owner_id=OWNER_ID,
            prefix="?",
        )

    async def event_oauth_authorized(
        self, payload: twitchio.authentication.UserTokenPayload
    ) -> None:
        """Se ejecuta cuando un usuario autoriza la aplicación."""
        await self.add_token(payload.access_token, payload.refresh_token)

        if not payload.user_id:
            return

        if payload.user_id == self.bot_id:
            LOGGER.info("[OK] Cuenta BOT autorizada (ID: %s)", payload.user_id)
            self._authorized.add("bot")
        else:
            LOGGER.info("[OK] Cuenta CANAL autorizada (ID: %s)", payload.user_id)
            self._authorized.add("canal")

        # Si ambas cuentas están autorizadas, cerrar automáticamente
        if {"bot", "canal"} <= self._authorized:
            LOGGER.info("")
            LOGGER.info("Ambas cuentas autorizadas. Cerrando setup...")
            await self.close()

    async def event_ready(self) -> None:
        """Muestra las instrucciones de autorización."""
        bot_scopes_str = "%20".join(BOT_SCOPES)
        channel_scopes_str = "%20".join(CHANNEL_SCOPES)

        url_bot = (
            f"http://localhost:4343/oauth?scopes={bot_scopes_str}&force_verify=true"
        )
        url_canal = (
            f"http://localhost:4343/oauth?scopes={channel_scopes_str}&force_verify=true"
        )

        LOGGER.info("=" * 60)
        LOGGER.info("SETUP: Servidor OAuth listo en http://localhost:4343")
        LOGGER.info("=" * 60)
        LOGGER.info("")
        LOGGER.info("Paso 1 - Autorizar cuenta BOT (%d scopes):", len(BOT_SCOPES))
        LOGGER.info("  %s", url_bot)
        LOGGER.info("")
        LOGGER.info("Paso 2 - Autorizar cuenta CANAL (%d scopes):", len(CHANNEL_SCOPES))
        LOGGER.info("  %s", url_canal)
        LOGGER.info("")
        LOGGER.info("Autoriza ambas cuentas. El setup se cerrará solo.")
        LOGGER.info("=" * 60)


def setup() -> None:
    """Punto de entrada del script de configuración."""
    setup_logging(level=logging.INFO)
    DB_DIR.mkdir(exist_ok=True)

    async def runner() -> None:
        async with asqlite.create_pool(str(DB_PATH)) as tdb:
            await setup_token_database(tdb)
            async with SetupBot(token_database=tdb) as bot:
                await bot.start(load_tokens=False)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOGGER.info("Setup finalizado.")


if __name__ == "__main__":
    setup()
