"""Entry point de bot-web: bot + servidor web en el mismo asyncio loop.

El terminal solo muestra logs del backend (conexión TwitchIO, web server).
Toda la visualización y control se hace desde la interfaz web.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from pathlib import Path

import uvicorn

from bot_tv.agent import TalkAgent
from bot_tv.bot import Bot
from bot_tv.database import (
    TokenRepository,
    create_app_db_pool,
    create_token_db_pool,
    run_app_migrations,
    run_token_migrations,
)
from bot_tv.event_bus import EventBus
from bot_tv.utils.env import DB_DIR, GEMINI_MODEL
from bot_tv.utils.logger import setup_logging
from bot_tv.web.server import WEB_PORT, create_app

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada de la aplicación web (sin REPL de terminal)."""
    setup_logging(level=logging.INFO)
    DB_DIR.mkdir(exist_ok=True)

    async def runner() -> None:
        async with (
            create_token_db_pool() as tdb,
            create_app_db_pool() as adb,
        ):
            await run_token_migrations(tdb)
            await run_app_migrations(adb)

            token_repo = TokenRepository(tdb)
            tokens, subs = await token_repo.load_tokens_and_subscriptions()

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

                agent = TalkAgent(bot, model=GEMINI_MODEL)
                await agent.initialize()

                app = create_app(bot, agent, event_bus)

                ssl_keyfile = None
                ssl_certfile = None
                certs_dir = Path("certs")
                if certs_dir.exists():
                    key_files = list(certs_dir.glob("*-key.pem"))
                    cert_files = [
                        f
                        for f in certs_dir.glob("*.pem")
                        if not f.name.endswith("-key.pem")
                    ]
                    if key_files and cert_files:
                        ssl_keyfile = str(key_files[0])
                        ssl_certfile = str(cert_files[0])
                        LOGGER.info(
                            "Configurando HTTPS local con certificados: %s y %s",
                            ssl_certfile,
                            ssl_keyfile,
                        )

                # Correr uvicorn en el mismo loop (sin iniciar un nuevo loop)
                config = uvicorn.Config(
                    app,
                    host="0.0.0.0",  # noqa: S104 — intencional para LAN
                    port=WEB_PORT,
                    log_level="info",
                    log_config=None,
                    loop="none",  # usamos el loop de asyncio existente
                    ssl_keyfile=ssl_keyfile,
                    ssl_certfile=ssl_certfile,
                )
                server = uvicorn.Server(config)
                app.state.server = server

                protocol = "https" if ssl_certfile else "http"
                LOGGER.info(
                    "Dashboard en %s://0.0.0.0:%d (LAN: busca tu IP local)",
                    protocol,
                    WEB_PORT,
                )

                bot_task = asyncio.create_task(bot.start(load_tokens=False))
                server_task = asyncio.create_task(server.serve())

                _done, pending = await asyncio.wait(
                    [bot_task, server_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Espera 2s para que la tarea restante termine limpiamente
                if pending:
                    _done_after, pending = await asyncio.wait(
                        pending,
                        timeout=2.0,
                    )

                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

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
