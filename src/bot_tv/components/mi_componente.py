from __future__ import annotations

import random
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

if TYPE_CHECKING:
    from bot_tv.bot import Bot


class MiComponente(commands.Component):
    """Componente con comandos y listeners del bot."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.Component.listener()
    async def event_message(self, payload: twitchio.ChatMessage) -> None:
        """Muestra en consola cada mensaje recibido."""
        print(f"[{payload.broadcaster.name}] {payload.chatter.name}: {payload.text}")

    @commands.command()
    async def hola(self, ctx: commands.Context) -> None:
        """Saluda al usuario que invoca el comando.  ?hola"""
        await ctx.reply(f"¡Hola {ctx.chatter}!")

    @commands.command()
    async def eleccion(self, ctx: commands.Context, *opciones: str) -> None:
        """Elige aleatoriamente entre las opciones dadas.  ?eleccion <a> <b> ..."""
        await ctx.reply(
            f"Elegí: {random.choice(opciones)}" if opciones else "Dame opciones!"
        )
