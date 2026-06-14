import asyncio
import logging

import twitchio

from bot_tv.database.app import (
    get_user_id_by_name,
    get_user_nickname,
    is_user_bot,
    upsert_user,
)
from bot_tv.utils.colors import (
    DIM,
    RESET,
    ROJO,
    VERDE,
    format_colored_name,
    get_chatter_rgb,
)

LOGGER = logging.getLogger(__name__)


class TwitchIRCClient:
    def __init__(
        self, bot, app_database, bot_username: str, token: str, canales: list[str]
    ) -> None:
        self.bot = bot
        self.app_database = app_database
        self.bot_username = bot_username.lower()
        if not token:
            raise ValueError("TwitchIRCClient requiere un token IRC válido.")
        # El token IRC DEBE empezar con "oauth:"
        self.token = f"oauth:{token}" if not token.startswith("oauth:") else token
        self.canales = [c.lower() for c in canales]
        self.writer: asyncio.StreamWriter | None = None
        self.reader: asyncio.StreamReader | None = None
        self.broadcaster: twitchio.PartialUser | None = None

    async def connect(self) -> None:
        """Conecta al servidor de IRC de Twitch y mantiene el loop."""
        LOGGER.info("Conectando a irc.chat.twitch.tv:6697...")
        try:
            # Obtener el broadcaster una vez al conectar
            try:
                broadcaster_id = self.bot.owner_id
                self.broadcaster = await self.bot.fetch_user(id=broadcaster_id)
            except Exception as e:
                LOGGER.error("Error al precargar broadcaster: %s", e)

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
        self,
        usuario: twitchio.PartialUser | None,
        broadcaster: twitchio.PartialUser | None,
    ) -> str:
        #! Teoricamente, nunca sucedera
        if usuario is None or broadcaster is None:
            return f"{DIM}(Desconocido){RESET}"

        if usuario.id == broadcaster.id:
            return f"{DIM}(Broadcaster){RESET}"

        if usuario.id == self.bot.bot_id:
            return f"{DIM}(Bot){RESET}"

        if await is_user_bot(self.app_database, usuario.id):
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
        display_name = usuario

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

        # Construir nombre coloreado
        r, g, b = get_chatter_rgb(None, usuario)
        if not twitch_user and not nickname:
            display_name = f"{{{usuario}}}"
        nombre_coloreado = format_colored_name(display_name, nickname, r, g, b)

        # Cargar broadcaster bajo demanda si falló la precarga en connect()
        if not self.broadcaster:
            try:
                broadcaster_id = self.bot.owner_id
                self.broadcaster = await self.bot.fetch_user(id=broadcaster_id)
            except Exception as e:
                LOGGER.error(
                    "Error al obtener broadcaster para id %s: %s",
                    self.bot.owner_id,
                    e,
                )

        try:
            elemento = await self._get_user_element(twitch_user, self.broadcaster)
        except Exception as e:
            LOGGER.error("Error al obtener elemento para %s: %s", usuario, e)
            elemento = f"{DIM}(Desconocido){RESET}"

        if action == "JOIN":
            accion_coloreada = f"{VERDE}JOIN{RESET}"
        else:
            accion_coloreada = f"{ROJO}PART{RESET}"

        LOGGER.info("%s %s: %s", nombre_coloreado, elemento, accion_coloreada)
