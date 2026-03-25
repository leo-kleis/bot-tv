from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from bot_tv.app_database import (
    get_user_id_by_name,
    get_user_nickname,
    is_user_bot,
    save_chat_message,
    set_nickname,
    set_user_bot,
    upsert_user,
)
from bot_tv.colors import (
    AMARILLO,
    DIM,
    RESET,
    format_colored_name,
    format_timestamp,
    get_chatter_rgb,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


class ChatComponent(commands.Component):
    """Componente de chat: mensajes en consola + comandos generales."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def _get_chatter_element(
        self, chatter: twitchio.Chatter, broadcaster_id: str | int
    ) -> str:
        """Determina el elemento (rol) del chatter.

        Prioridad:
        1. Broadcaster → '(Broadcaster)'
        2. Nuestro bot → '(Bot)'
        3. Bot marcado en DB → '(Bot)'
        4. Seguidor → '(DD/MM/AA)' con la fecha de follow
        5. Ninguno → '(Visita)'
        """
        user_id = str(chatter.id)

        # 1. Es el broadcaster del canal
        if chatter.id == broadcaster_id:
            return f"{DIM}(Broadcaster){RESET}"

        # 2. Es nuestro bot
        if user_id == self.bot.bot_id:
            return f"{DIM}(Bot){RESET}"

        # 3. Está marcado como bot en la DB
        if await is_user_bot(self.bot.app_database, user_id):
            return f"{DIM}(Bot){RESET}"

        # 4. Es seguidor (consulta en tiempo real)
        follow = await chatter.follow_info()
        if follow and follow.followed_at:
            fecha = follow.followed_at.strftime("%d/%m/%y")
            return f"{DIM}({fecha}){RESET}"

        # 5. No es seguidor
        return f"{DIM}(Visita){RESET}"

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

        # Obtener valores RGB del color de Twitch del chatter, o uno por defecto
        # pasándole el nombre de usuario (para que asigne consistentemente un color).
        hex_str = str(chatter.color.hex) if chatter.color else None
        r, g, b = get_chatter_rgb(hex_str, username)
        nombre_coloreado = format_colored_name(display_name, nickname, r, g, b)

        timestamp = format_timestamp()

        # Elemento (rol del chatter)
        elemento = await self._get_chatter_element(chatter, payload.broadcaster.id)

        print(f"{timestamp} {nombre_coloreado} {elemento}: {payload.text}")

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

    async def _resolve_user(
        self, comando: str, usuario: str
    ) -> str | None:
        """Busca el user_id de un usuario en la DB local o en la API de Twitch.

        Si no existe en la DB, lo busca en Twitch y lo registra.
        Retorna el user_id o None si no se encontró.
        """
        user_id = await get_user_id_by_name(
            self.bot.app_database, usuario
        )
        if user_id:
            return user_id

        LOGGER.info(
            "%s: usuario '%s%s%s' no existe en la base de datos. "
            "Buscando en Twitch...",
            comando,
            AMARILLO,
            usuario,
            RESET,
        )
        twitch_user = await self.bot.fetch_user(login=usuario)
        if not twitch_user:
            LOGGER.warning(
                "%s: usuario '%s%s%s' no encontrado en Twitch.",
                comando,
                AMARILLO,
                usuario,
                RESET,
            )
            return None

        user_id = str(twitch_user.id)
        await upsert_user(
            self.bot.app_database,
            user_id,
            twitch_user.name,
            twitch_user.display_name,
        )
        return user_id

    @commands.command()
    @commands.is_broadcaster()
    async def bot(self, ctx: commands.Context, usuario: str) -> None:
        """Marca o desmarca un usuario como bot.  ?bot <usuario>"""
        if not usuario:
            LOGGER.warning("bot: no se proporcionó un usuario válido.")
            return

        usuario = usuario.lower()
        user_id = await self._resolve_user("Bot", usuario)
        if not user_id:
            return

        # Toggle: si ya es bot, desmarcarlo; si no, marcarlo
        es_bot = await is_user_bot(self.bot.app_database, user_id)
        await set_user_bot(self.bot.app_database, user_id, not es_bot)

        # Respuesta solo en terminal
        usuario_coloreado = f"{AMARILLO}{usuario}{RESET}"
        if es_bot:
            LOGGER.info("%s ya no está marcado como bot.", usuario_coloreado)
        else:
            LOGGER.warning("%s fue marcado como bot.", usuario_coloreado)

    @commands.command()
    @commands.is_broadcaster()
    async def apodo(
        self, ctx: commands.Context, usuario: str, apodo: str | None = None
    ) -> None:
        """Asigna o elimina un apodo.  ?apodo <usuario> [apodo]"""
        if not usuario:
            LOGGER.warning("apodo: no se proporcionó un usuario válido.")
            return

        usuario = usuario.lower()
        user_id = await self._resolve_user("Apodo", usuario)
        if not user_id:
            return

        # Establecer el apodo en la base de datos
        await set_nickname(self.bot.app_database, user_id, apodo)

        # Respuesta solo en terminal
        usuario_coloreado = f"{AMARILLO}{usuario}{RESET}"
        if apodo:
            LOGGER.info("Apodo de %s cambiado a: %s", usuario_coloreado, apodo)
        else:
            LOGGER.info("Apodo de %s eliminado.", usuario_coloreado)

    async def component_command_error(
        self, payload: commands.CommandErrorPayload
    ) -> None:
        """Captura errores de comandos dentro de este componente."""
        error = payload.exception
        ctx = payload.context

        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            LOGGER.warning(
                "Faltan argumentos o son inválidos en '?%s': %s",
                ctx.command.name if ctx.command else "?",
                error,
            )
            return

        # Cualquier otro error no manejado lo registramos completo
        LOGGER.exception(
            "Error no manejado en '?%s'",
            ctx.command.name if ctx.command else "?",
            exc_info=error,
        )
