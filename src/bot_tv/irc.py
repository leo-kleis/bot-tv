import asyncio
import logging
from datetime import datetime

import twitchio

from bot_tv.app_database import (
    get_user_id_by_name,
    get_user_nickname,
    is_user_bot,
    upsert_user,
)

LOGGER = logging.getLogger(__name__)

# Códigos ANSI para la terminal
VERDE = "\033[92m"
ROJO = "\033[91m"
RESET = "\033[0m"
DIM = "\033[2m"
# Color fijo para el timestamp [HH:MM:SS]
TIMESTAMP_COLOR = "\033[38;2;94;79;247m"

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


def _get_rgb_from_hex(hex_color: str | None) -> tuple[int, int, int] | None:
    if not hex_color:
        return None
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


def _get_chatter_rgb(hex_color: str | None, username: str) -> tuple[int, int, int]:
    if hex_color:
        rgb = _get_rgb_from_hex(hex_color)
        if rgb:
            return rgb
    indice = sum(ord(c) for c in username) % len(TWITCH_DEFAULT_COLORS)
    return TWITCH_DEFAULT_COLORS[indice]


class TwitchIRCClient:
    def __init__(
        self, bot, app_database, bot_username: str, token: str, canales: list[str]
    ) -> None:
        self.bot = bot
        self.app_database = app_database
        self.bot_username = bot_username.lower()
        # El token IRC DEBE empezar con "oauth:"
        self.token = f"oauth:{token}" if not token.startswith("oauth:") else token
        self.canales = [c.lower() for c in canales]
        self.writer: asyncio.StreamWriter | None = None
        self.reader: asyncio.StreamReader | None = None

    async def connect(self) -> None:
        """Conecta al servidor de IRC de Twitch y mantiene el loop."""
        LOGGER.info("Conectando a irc.chat.twitch.tv:6697...")
        try:
            self.reader, self.writer = await asyncio.open_connection(
                "irc.chat.twitch.tv", 6697, ssl=True
            )

            # Autenticación
            self._send(f"PASS {self.token}")
            self._send(f"NICK {self.bot_username}")

            # Pedir compatibilidad para recibir JOIN y PART
            self._send("CAP REQ :twitch.tv/membership")

            # Unirse a todos los canales
            for canal in self.canales:
                self._send(f"JOIN #{canal}")

            canales_str = ", ".join(self.canales)
            LOGGER.info("Autenticado y escuchando JOIN/PART en: %s", canales_str)

            await self._listen()

        except Exception as e:
            LOGGER.exception("Error en la conexión IRC: %s", e)

    def _send(self, message: str) -> None:
        if self.writer:
            self.writer.write(f"{message}\r\n".encode())

    async def _listen(self) -> None:
        if not self.reader:
            return

        while not self.reader.at_eof():
            try:
                line_bytes = await self.reader.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace").strip()

                if line.startswith("PING"):
                    self._send(line.replace("PING", "PONG", 1))
                    continue

                await self._process_line(line)
            except Exception as e:
                LOGGER.error("Error procesando línea: %s", e)

        LOGGER.warning("Conexión cerrada.")

    async def _process_line(self, line: str) -> None:
        # Formato de JOIN/PART: :usuario!usuario@usuario.tmi.twitch.tv JOIN/PART #canal

        # Ignorar mensajes internos del servidor si no tienen estructura usuario!usuario
        if "!" not in line or "@" not in line:
            return

        partes = line.split("!")
        if len(partes) > 1 and partes[0].startswith(":"):
            usuario = partes[0][1:].lower()

            # Buscamos de qué acción se trata y en qué canal
            if " JOIN #" in line:
                await self._handle_event(usuario, "JOIN")
            elif " PART #" in line:
                await self._handle_event(usuario, "PART")

    async def _get_user_element(
        self, usuario: twitchio.PartialUser | None, broadcaster: twitchio.PartialUser
    ) -> str:
        #! Teoricamente, nunca sucedera
        if usuario is None:
            return f"{DIM}(Desconocido){RESET}"

        if usuario.id == broadcaster.id:
            return f"{DIM}(Broadcaster){RESET}"

        if usuario.id == self.bot.bot_id:
            return f"{DIM}(Bot){RESET}"

        if await is_user_bot(self.app_database, str(usuario.id)):
            return f"{DIM}(Bot){RESET}"

        follow = await broadcaster.fetch_followers(user=usuario, first=1)
        async for event in follow.followers:
            fecha = event.followed_at.strftime("%d/%m/%y")
            return f"{DIM}({fecha}){RESET}"

        return f"{DIM}(Visita){RESET}"

    async def _handle_event(self, usuario: str, action: str) -> None:
        # Ignorar al bot mismo si no queremos procesarlo cada vez
        if usuario == self.bot_username:
            return

        # 1. Verificar existencia local en SQLite
        user_id = await get_user_id_by_name(self.app_database, usuario)
        display_name = f"{{{usuario}}}"

        # Obtener el PartialUser de Twitch (necesario para verificar follow, bot, etc.)
        twitch_user = None
        try:
            twitch_user = await self.bot.fetch_user(login=usuario)
            if twitch_user:
                display_name = twitch_user.display_name
                if not user_id and action == "JOIN":
                    user_id = str(twitch_user.id)
                    # 3. Guardar en SQLite local
                    await upsert_user(
                        self.app_database,
                        user_id,
                        twitch_user.name,
                        display_name,
                    )
        except Exception as e:
            LOGGER.error("Error al buscar fetch_user para %s: %s", usuario, e)

        # Obtener apodo de la base de datos si user_id existe
        nickname = None
        if user_id:
            nickname = await get_user_nickname(self.app_database, user_id)

        # Construir nombre coloreado igual que en event_message
        r, g, b = _get_chatter_rgb(None, usuario)
        color_ansi = f"\033[38;2;{r};{g};{b}m"

        if nickname:
            dark_r, dark_g, dark_b = int(r * 0.5), int(g * 0.5), int(b * 0.5)
            dark_ansi = f"\033[38;2;{dark_r};{dark_g};{dark_b}m"
            nombre_coloreado = (
                f"{color_ansi}{nickname}{dark_ansi} {{{display_name}}}{RESET}"
            )
        else:
            nombre_coloreado = f"{color_ansi}{display_name}{RESET}"

        # Imprimir en consola con la hora, colores y formato solicitados
        hora = datetime.now().strftime("%H:%M:%S")
        timestamp = f"{TIMESTAMP_COLOR}[{hora}]{RESET}"

        broadcaster_id = self.bot.owner_id
        broadcaster = await self.bot.fetch_user(id=broadcaster_id)

        try:
            elemento = await self._get_user_element(twitch_user, broadcaster)
        except Exception as e:
            LOGGER.error("Error al obtener elemento para %s: %s", usuario, e)
            elemento = f"{DIM}(Desconocido){RESET}"

        if action == "JOIN":
            accion_coloreada = f"{VERDE}JOIN{RESET}"
        else:
            accion_coloreada = f"{ROJO}PART{RESET}"

        print(f"{timestamp} {nombre_coloreado} {elemento}: {accion_coloreada}")
