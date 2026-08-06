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
    create_pg_pool,
)
from bot_tv.event_bus import EventBus
from bot_tv.utils.env import GEMINI_MODEL
from bot_tv.utils.logger import setup_logging
from bot_tv.web.server import WEB_PORT, create_app

LOGGER = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada de la aplicación web (sin REPL de terminal)."""
    setup_logging(level=logging.INFO)

    async def runner() -> None:
        LOGGER.info("Iniciando servidor bot-web...")
        try:
            LOGGER.info("Conectando a la base de datos PostgreSQL...")
            try:
                pool = await create_pg_pool()
            except Exception as exc:
                LOGGER.critical(
                    "No se pudo conectar a la base de datos PostgreSQL: %s. "
                    "Verifica que la base de datos esté activa y que "
                    "la variable DATABASE_URL sea correcta.",
                    exc,
                )
                sys.exit(1)
            LOGGER.info("Conexión con PostgreSQL establecida.")

            try:
                LOGGER.info("Cargando tokens de autenticación y suscripciones...")
                token_repo = TokenRepository(pool)
                tokens, subs = await token_repo.load_tokens_and_subscriptions()

                if not tokens:
                    LOGGER.error(
                        "No se encontraron tokens en la base de datos. "
                        "Ejecutá primero: uv run bot-setup"
                    )
                    sys.exit(1)

                LOGGER.info("Tokens cargados: %d", len(tokens))

                from bot_tv.utils.network import (
                    check_twitch_connection,
                    get_port_process_info,
                    is_port_in_use,
                )

                LOGGER.info("Verificando disponibilidad del puerto web %d...", WEB_PORT)
                if is_port_in_use(WEB_PORT):
                    info = get_port_process_info(WEB_PORT)
                    if info:
                        pid, process_name = info
                        LOGGER.critical(
                            "El puerto %d está ocupado por el proceso '%s' (PID: %d). "
                            "Cerrá ese proceso antes de ejecutar bot-web.",
                            WEB_PORT,
                            process_name,
                            pid,
                        )
                    else:
                        LOGGER.critical(
                            "El puerto %d ya está en uso por otro proceso o instancia. "
                            "Cerrá la instancia anterior o libera el puerto antes "
                            "de ejecutar bot-web.",
                            WEB_PORT,
                        )
                    sys.exit(1)

                LOGGER.info("Verificando conexión con la API de Twitch...")
                if not check_twitch_connection():
                    LOGGER.critical(
                        "No se pudo establecer conexión con Twitch (id.twitch.tv). "
                        "Por favor, verifica tu conexión a internet o la "
                        "configuración de DNS/red. "
                        "El inicio del bot ha sido cancelado para evitar "
                        "congelamientos."
                    )
                    sys.exit(1)

                LOGGER.info("Inicializando cliente de Twitch y agente de IA...")
                event_bus = EventBus()

                async with Bot(
                    database=pool,
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

                    config = uvicorn.Config(
                        app,
                        host="0.0.0.0",  # noqa: S104
                        port=WEB_PORT,
                        log_level="info",
                        log_config=None,
                        loop="none",
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

                    if pending:
                        _done_after, pending = await asyncio.wait(
                            pending,
                            timeout=2.0,
                        )

                    for task in pending:
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task
            finally:
                await pool.close()
        finally:
            import gc

            gc.collect()
            await asyncio.sleep(0.25)

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
