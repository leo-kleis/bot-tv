from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from bot_tv.app_database import (
    get_user_nickname,
    save_chat_message,
    upsert_user,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)

# Códigos ANSI
RESET = "\033[0m"

# Color fijo para el timestamp [HH:MM:SS]
TIMESTAMP_COLOR = "\033[38;2;94;79;247m"  # #5E4FF7

# Color por defecto para chatters sin color personalizado
DEFAULT_NAME_COLOR = "\033[38;2;232;148;58m"  # #E8943A (anaranjado)


def _hex_to_ansi(hex_color: str | None) -> str:
    """Convierte un color hex a código ANSI truecolor (24-bit).

    Soporta formatos: '#RRGGBB', '0xRRGGBB', 'RRGGBB'.
    TwitchIO usa formato '0xRRGGBB' internamente.
    Si el color es None o inválido, devuelve string vacío (sin color).
    """
    if not hex_color:
        return ""
    # Limpiar prefijos conocidos
    hex_color = hex_color.removeprefix("#").removeprefix("0x")
    if len(hex_color) != 6:
        return ""
    try:
        r, g, b = (
            int(hex_color[:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:], 16),
        )
    except ValueError:
        return ""
    # \033[38;2;R;G;Bm = foreground truecolor
    return f"\033[38;2;{r};{g};{b}m"


class MiComponente(commands.Component):
    """Componente con comandos y listeners del bot."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.Component.listener()
    async def event_message(self, payload: twitchio.ChatMessage) -> None:
        """Guarda el mensaje en el historial y muestra en consola con color."""
        chatter = payload.chatter
        user_id = str(chatter.id)
        username = chatter.name or user_id
        display_name = chatter.display_name or username

        # Guardar/actualizar datos del usuario en la DB
        await upsert_user(self.bot.app_database, user_id, username, display_name)

        # Guardar el mensaje en el historial
        await save_chat_message(
            self.bot.app_database,
            str(payload.broadcaster.id),
            user_id,
            payload.text,
        )

        # Determinar nombre a mostrar: apodo > display_name
        nickname = await get_user_nickname(self.bot.app_database, user_id)
        nombre = nickname or display_name

        # Timestamp local [HH:MM:SS] con color fijo
        hora = datetime.now().strftime("%H:%M:%S")
        timestamp = f"{TIMESTAMP_COLOR}[{hora}]{RESET}"

        # Nombre coloreado con el color de Twitch del chatter
        color_ansi = _hex_to_ansi(str(chatter.color) if chatter.color else None)
        color_ansi = color_ansi or DEFAULT_NAME_COLOR
        nombre_coloreado = f"{color_ansi}{nombre}{RESET}"

        print(f"{timestamp} {nombre_coloreado}: {payload.text}")

    @commands.command()
    async def hola(self, ctx: commands.Context) -> None:
        """Saluda al usuario que invoca el comando.  ?hola"""
        await ctx.reply(f"¡Hola {ctx.chatter}!")

    @commands.command()
    async def eleccion(self, ctx: commands.Context, *opciones: str) -> None:
        """Elige aleatoriamente entre las opciones dadas.  ?eleccion <a> <b> ..."""
        import random

        await ctx.reply(
            f"Elegí: {random.choice(opciones)}" if opciones else "Dame opciones!"
        )
