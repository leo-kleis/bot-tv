"""Entry point de bot-web: bot + servidor web en el mismo asyncio loop.

El terminal solo muestra logs del backend (conexión TwitchIO, web server).
Toda la visualización y control se hace desde la interfaz web.
"""

from __future__ import annotations

import asyncio
import logging
import sys

import asqlite
import uvicorn

from bot_tv.bot import Bot
from bot_tv.database.app import APP_DB_PATH, setup_app_database
from bot_tv.database.tokens import DB_PATH, setup_token_database
from bot_tv.event_bus import EventBus
from bot_tv.utils.env import DB_DIR
from bot_tv.utils.logger import setup_logging
from bot_tv.web.server import WEB_PORT, create_app

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada de la aplicación web (sin REPL de terminal)."""
    setup_logging(level=logging.INFO)
    DB_DIR.mkdir(exist_ok=True)

    async def runner() -> None:
        async with (
            asqlite.create_pool(str(DB_PATH)) as tdb,
            asqlite.create_pool(str(APP_DB_PATH)) as adb,
        ):
            tokens, subs = await setup_token_database(tdb)
            await setup_app_database(adb)

            if not tokens:
                LOGGER.error(
                    "No se encontraron tokens en la base de datos. "
                    "Ejecutá primero: uv run bot-setup"
                )
                sys.exit(1)

            LOGGER.info("Tokens cargados: %d", len(tokens))

            event_bus = EventBus()
            # bot-web no crea TerminalConsumer — el output Rich no se usa

            async with Bot(
                token_database=tdb,
                app_database=adb,
                subs=subs,
                event_bus=event_bus,
            ) as bot:
                for pair in tokens:
                    await bot.add_token(*pair)

                # Inicializar TalkAgent
                from bot_tv.agent import TalkAgent
                from bot_tv.utils.env import GEMINI_MODEL

                agent = TalkAgent(bot, model=GEMINI_MODEL)
                await agent.initialize()

                app = create_app(bot, agent, event_bus)

                # Correr uvicorn en el mismo loop (sin iniciar un nuevo loop)
                config = uvicorn.Config(
                    app,
                    host="0.0.0.0",  # noqa: S104 — intencional para LAN
                    port=WEB_PORT,
                    log_level="info",
                    loop="none",  # usamos el loop de asyncio existente
                )
                server = uvicorn.Server(config)
                app.state.server = server

                LOGGER.info(
                    "Dashboard en http://0.0.0.0:%d (LAN: busca tu IP local)",
                    WEB_PORT,
                )

                await asyncio.gather(
                    bot.start(load_tokens=False),
                    server.serve(),
                )

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        LOGGER.warning("Apagando bot-web...")
    except RuntimeError as e:
        if "Unable to associate shards with Conduit" in str(e):
            LOGGER.error(
                "Error de conexión con Twitch (EventSub Conduit). "
                "Esto suele ser temporal. Reintentá en unos instantes."
            )
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
