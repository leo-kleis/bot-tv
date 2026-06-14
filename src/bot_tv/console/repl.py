from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from bot_tv.agent import TalkAgent
from bot_tv.console.commands import AdminCommands
from bot_tv.console.completer import BotCompleter
from bot_tv.utils.colors import CONSOLE
from bot_tv.utils.env import GEMINI_MODEL

if TYPE_CHECKING:
    from bot_tv.bot import Bot

print = CONSOLE.print

LOGGER = logging.getLogger(__name__)


class AdminConsole:
    """Consola administrativa REPL interactiva."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.agent = TalkAgent(bot, model=GEMINI_MODEL)
        self.commands = AdminCommands(bot, self.agent)
        self.session = PromptSession(completer=BotCompleter(bot))

    async def run(self) -> None:
        """Inicia el loop REPL asíncrono una vez que el bot esté listo."""
        try:
            # Esperar a que el bot esté completamente conectado
            await self.bot.wait_for("bot_fully_connected")
        except Exception:
            await asyncio.sleep(2)

        LOGGER.info(
            "Consola administrativa iniciada. Escribe 'help' para ver comandos."
        )

        # Inicializar el agente cargando configuraciones e historial de la DB
        await self.agent.initialize()

        with patch_stdout(raw=True):
            while True:
                try:
                    # Leer entrada del usuario
                    text = await self.session.prompt_async("bot-tv> ")
                    text = text.strip()
                    if not text:
                        continue

                    parts = text.split()
                    cmd = parts[0].lower()
                    args = parts[1:]

                    if cmd == "exit":
                        await self.commands.exit()
                        break
                    elif cmd == "help":
                        self.commands.help()
                    elif cmd == "sync_followers":
                        await self.commands.sync_followers()
                    elif cmd == "is_bot":
                        await self.commands.is_bot(args)
                    elif cmd == "apodo":
                        await self.commands.apodo(args)
                    elif cmd == "talk":
                        await self._cmd_talk(args)
                    elif cmd == "rpm":
                        self.commands.rpm(args)
                    elif cmd == "model":
                        self.commands.model(args)
                    elif cmd == "models":
                        self.commands.models()
                    else:
                        print(
                            f"Comando desconocido: '{cmd}'. "
                            f"Escribe 'help' para ver la lista."
                        )
                except KeyboardInterrupt, EOFError:
                    await self.commands.exit()
                    break
                except Exception as e:
                    LOGGER.exception("Error al procesar comando en consola: %s", e)

    async def _cmd_talk(self, args: list[str]) -> None:
        """Envía una pregunta o solicitud al agente de IA."""
        if not args:
            LOGGER.warning("talk: se requiere un mensaje.")
            return

        mensaje = " ".join(args)
        LOGGER.info("Consultando al agente de IA...")

        with CONSOLE.status("[bold cyan]Pensando[/bold cyan]", spinner="dots"):
            respuesta = await self.agent.chat(mensaje)

        # Limpiar marcas de formato Markdown para la consola
        import re

        respuesta = re.sub(r"\*\*|__", "", respuesta)
        respuesta = re.sub(r"\*|_", "", respuesta)
        respuesta = re.sub(r"`", "", respuesta)

        from bot_tv.utils.colors import format_timestamp

        print(f"\n{format_timestamp()} {respuesta}\n")
