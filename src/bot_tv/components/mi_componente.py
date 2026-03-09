from __future__ import annotations

import logging
import random
from datetime import datetime
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

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)

# Códigos ANSI
RESET = "\033[0m"
DIM = "\033[2m"
AMARILLO = "\033[33m"

# Color fijo para el timestamp [HH:MM:SS]
TIMESTAMP_COLOR = "\033[38;2;94;79;247m"  # #5E4FF7

# Colores por defecto de Twitch (RGB) para usuarios sin color configurado
TWITCH_DEFAULT_COLORS = [
    (255, 0, 0),  # Red
    (0, 0, 255),  # Blue
    (0, 128, 0),  # Green
    (178, 34, 34),  # FireBrick
    (255, 127, 80),  # Coral
    (154, 205, 50),  # YellowGreen
    (255, 69, 0),  # OrangeRed
    (46, 139, 87),  # SeaGreen
    (218, 165, 32),  # GoldenRod
    (210, 105, 30),  # Chocolate
    (95, 158, 160),  # CadetBlue
    (30, 144, 255),  # DodgerBlue
    (255, 105, 180),  # HotPink
    (138, 43, 226),  # BlueViolet
    (0, 255, 127),  # SpringGreen
]


def _get_chatter_rgb(hex_color: str | None, username: str) -> tuple[int, int, int]:
    """Obtiene el color en tupla (r, g, b) desde el color hex de Twitch.
    Si el usuario no tiene color (hex_color es None), se le asigna uno
    por defecto de la misma manera determinista que lo hace el chat oficial de Twitch.
    """
    if hex_color:
        rgb = _get_rgb_from_hex(hex_color)
        if rgb:
            return rgb

    # Determinista: sumar el valor de cada carácter y sacar módulo % 15
    indice = sum(ord(char) for char in username) % len(TWITCH_DEFAULT_COLORS)
    return TWITCH_DEFAULT_COLORS[indice]


def _get_rgb_from_hex(hex_color: str | None) -> tuple[int, int, int] | None:
    """Convierte un color hex a una tupla RGB (r, g, b).

    Soporta formatos: '#RRGGBB', '0xRRGGBB', 'RRGGBB'.
    Si el color es None o inválido, devuelve None.
    """
    if not hex_color:
        return None
    # Limpiar prefijos conocidos
    hex_color = hex_color.removeprefix("#").removeprefix("0x")
    if len(hex_color) != 6:
        return None
    try:
        return (
            int(hex_color[:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:], 16),
        )
    except ValueError:
        return None


class MiComponente(commands.Component):
    """Componente con comandos y listeners del bot."""

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
        r, g, b = _get_chatter_rgb(hex_str, username)
        color_ansi = f"\033[38;2;{r};{g};{b}m"

        if nickname:
            # Si tiene apodo, mostrar: Apodo{display_name}
            # Multiplicamos el RGB por 0.5 para hacerlo más oscuro manualmente.
            dark_r, dark_g, dark_b = int(r * 0.5), int(g * 0.5), int(b * 0.5)
            dark_ansi = f"\033[38;2;{dark_r};{dark_g};{dark_b}m"

            nombre_coloreado = (
                f"{color_ansi}{nickname}{dark_ansi} {{{display_name}}}{RESET}"
            )
        else:
            nombre_coloreado = f"{color_ansi}{display_name}{RESET}"

        # Timestamp local [HH:MM:SS] con color fijo
        hora = datetime.now().strftime("%H:%M:%S")
        timestamp = f"{TIMESTAMP_COLOR}[{hora}]{RESET}"

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

    @commands.command()
    @commands.is_broadcaster()
    async def bot(self, ctx: commands.Context, usuario: str) -> None:
        """Marca o desmarca un usuario como bot.  ?bot <usuario>"""
        if not usuario:
            LOGGER.warning("bot: no se proporcionó un usuario válido.")
            return

        usuario = usuario.lower()

        # Buscar si el usuario existe en nuestra base de datos
        user_id = await get_user_id_by_name(self.bot.app_database, usuario)

        if not user_id:
            LOGGER.info(
                "Bot: usuario '%s%s%s' no existe en la base de datos. "
                "Buscando en Twitch...",
                AMARILLO,
                usuario,
                RESET,
            )
            # Buscar el usuario en la API de Twitch
            twitch_user = await self.bot.fetch_user(login=usuario)
            if not twitch_user:
                LOGGER.warning(
                    "Bot: usuario '%s%s%s' no encontrado en Twitch.",
                    AMARILLO,
                    usuario,
                    RESET,
                )
                return

            user_id = twitch_user.id
            username = twitch_user.name
            display_name = twitch_user.display_name

            # Guardarlo en la base de datos para futuras consultas
            await upsert_user(self.bot.app_database, user_id, username, display_name)

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

        # Buscar si el usuario existe en nuestra base de datos
        user_id = await get_user_id_by_name(self.bot.app_database, usuario)

        if not user_id:
            LOGGER.info(
                "Apodo: usuario '%s%s%s' no existe en la base de datos. "
                "Buscando en Twitch...",
                AMARILLO,
                usuario,
                RESET,
            )
            # Buscar el usuario en la API de Twitch
            twitch_user = await self.bot.fetch_user(login=usuario)
            if not twitch_user:
                LOGGER.warning(
                    "Apodo: usuario '%s%s%s' no encontrado en Twitch.",
                    AMARILLO,
                    usuario,
                    RESET,
                )
                return

            user_id = str(twitch_user.id)
            username = twitch_user.name
            display_name = twitch_user.display_name

            # Guardarlo en la base de datos para futuras consultas
            await upsert_user(self.bot.app_database, user_id, username, display_name)

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
