import asyncio
import logging

import asqlite
import twitchio
from twitchio.ext import commands

from bot_tv.database import DB_DIR, DB_PATH, save_token, setup_database
from bot_tv.env import BOT_ID, CLIENT_ID, CLIENT_SECRET, OWNER_ID

LOGGER = logging.getLogger(__name__)


class SetupBot(commands.AutoBot):
    """Cliente mínimo para autorizar cuentas y guardar tokens."""

    def __init__(self, *, token_database: asqlite.Pool) -> None:
        self.token_database = token_database

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
        else:
            LOGGER.info("[OK] Cuenta CANAL autorizada (ID: %s)", payload.user_id)

    async def add_token(
        self, token: str, refresh: str
    ) -> twitchio.authentication.ValidateTokenPayload:
        """Añade y persiste un token de acceso en la base de datos."""
        resp = await super().add_token(token, refresh)
        if resp.user_id:
            await save_token(self.token_database, resp.user_id, token, refresh)
            LOGGER.info("Token guardado para el usuario: %s", resp.user_id)
        return resp

    async def event_ready(self) -> None:
        """Muestra las instrucciones de autorización."""
        LOGGER.info("=" * 60)
        LOGGER.info("SETUP: Servidor OAuth listo en http://localhost:4343")
        LOGGER.info("=" * 60)
        LOGGER.info("")
        LOGGER.info("Paso 1 - Autorizar cuenta BOT:")
        LOGGER.info(
            "  Abrí en modo incógnito: "
            "http://localhost:4343/oauth?scopes="
            "user:read:chat%%20user:write:chat%%20user:bot"
            "&force_verify=true"
        )
        LOGGER.info("")
        LOGGER.info("Paso 2 - Autorizar cuenta CANAL:")
        LOGGER.info(
            "  Abrí en tu navegador: "
            "http://localhost:4343/oauth?scopes="
            "channel:bot%%20user:read:chat"
            "&force_verify=true"
        )
        LOGGER.info("")
        LOGGER.info("Cuando termines, presioná Ctrl+C para salir.")
        LOGGER.info("=" * 60)


def setup() -> None:
    """Punto de entrada del script de configuración."""
    twitchio.utils.setup_logging(level=logging.INFO)
    DB_DIR.mkdir(exist_ok=True)

    async def runner() -> None:
        async with asqlite.create_pool(str(DB_PATH)) as tdb:
            await setup_database(tdb)
            async with SetupBot(token_database=tdb) as bot:
                await bot.start(load_tokens=False)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOGGER.info("Setup finalizado.")


if __name__ == "__main__":
    setup()
