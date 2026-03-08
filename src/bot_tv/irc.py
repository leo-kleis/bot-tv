import asyncio
import logging
from datetime import datetime

from bot_tv.app_database import get_user_id_by_name, get_user_nickname, upsert_user

LOGGER = logging.getLogger(__name__)

# Códigos ANSI para la terminal
VERDE = "\033[92m"
ROJO = "\033[91m"
RESET = "\033[0m"
# Color fijo para el timestamp [HH:MM:SS]
TIMESTAMP_COLOR = "\033[38;2;94;79;247m"


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

    async def _handle_event(self, usuario: str, action: str) -> None:
        # Ignorar al bot mismo si no queremos procesarlo cada vez
        if usuario == self.bot_username:
            return

        # 1. Verificar existencia local en SQLite
        user_id = await get_user_id_by_name(self.app_database, usuario)
        display_name = usuario

        # Lógica especial para guardar al usuario la primera vez que hace
        # un evento (como JOIN)
        if not user_id and action == "JOIN":
            try:
                twitch_user = await self.bot.fetch_user(login=usuario)
                if twitch_user:
                    user_id = str(twitch_user.id)
                    display_name = twitch_user.display_name
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
        apodo_texto = ""
        if user_id:
            nickname = await get_user_nickname(self.app_database, user_id)
            if nickname:
                apodo_texto = f" - {nickname}"

        # 4. Imprimir en consola con la hora, colores y formato solicitados
        hora = datetime.now().strftime("%H:%M:%S")
        timestamp = f"{TIMESTAMP_COLOR}[{hora}]{RESET}"

        if action == "JOIN":
            print(f"{timestamp} {VERDE}JOIN{RESET} {usuario}{apodo_texto}")
        elif action == "PART":
            print(f"{timestamp} {ROJO}PART{RESET} {usuario}{apodo_texto}")
