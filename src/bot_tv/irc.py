import asyncio
import contextlib
import logging
from datetime import datetime

import twitchio

from bot_tv.events import TwitchIRCStatusEvent, UserJoinEvent, UserPartEvent
from bot_tv.utils.colors import get_chatter_rgb

LOGGER = logging.getLogger(__name__)


class TwitchIRCClient:
    def __init__(
        self, bot, database, bot_username: str, token: str, canales: list[str]
    ) -> None:
        self.bot = bot
        self.database = database
        self.bot_username = bot_username.lower()
        if not token:
            raise ValueError("TwitchIRCClient requiere un token IRC válido.")
        self.token = f"oauth:{token}" if not token.startswith("oauth:") else token
        self.canales = [c.lower() for c in canales]
        self.writer: asyncio.StreamWriter | None = None
        self.reader: asyncio.StreamReader | None = None
        self.broadcaster: twitchio.PartialUser | None = None
        self.connected_event = asyncio.Event()
        self.connected_users: dict[str, UserJoinEvent] = {}
        self._running = True
        self.is_connected = False

    async def _emit_status(self, connected: bool) -> None:
        """Emite el estado actual de la conexión de IRC al EventBus."""
        await self.bot.event_bus.emit(TwitchIRCStatusEvent(connected=connected))

    async def connect(self) -> None:
        """Conecta al servidor de IRC de Twitch y mantiene el loop con reconexiones."""
        self._running = True
        backoff = 2.0

        while self._running:
            self.connected_users.clear()
            self.is_connected = False
            self.connected_event.clear()
            await self._emit_status(connected=False)

            LOGGER.info("Conectando a irc.chat.twitch.tv:6697...")
            try:
                try:
                    if not self.broadcaster:
                        broadcaster_id = self.bot.owner_id
                        self.broadcaster = await self.bot.fetch_user(id=broadcaster_id)
                except Exception as e:
                    LOGGER.error("Error al precargar broadcaster: %s", e)

                self.reader, self.writer = await asyncio.open_connection(
                    "irc.chat.twitch.tv", 6697, ssl=True
                )

                self._send(f"PASS {self.token}")
                self._send(f"NICK {self.bot_username}")
                self._send("CAP REQ :twitch.tv/membership")

                for canal in self.canales:
                    self._send(f"JOIN #{canal}")

                canales_str = ", ".join(self.canales)
                LOGGER.info("Autenticado y escuchando JOIN/PART en: %s", canales_str)

                self.is_connected = True
                self.connected_event.set()
                await self._emit_status(connected=True)

                backoff = 2.0  # Resetear el backoff tras conexión exitosa

                await self._listen()

            except Exception as e:
                LOGGER.exception(
                    "Error en la conexión IRC (reintentando en %.1fs): %s",
                    backoff,
                    e,
                )
                self.connected_event.set()  # Evitar bloquear el arranque del bot

            self.is_connected = False
            await self._emit_status(connected=False)

            if self.writer:
                with contextlib.suppress(Exception):
                    self.writer.close()
                    await self.writer.wait_closed()
                self.writer = None
            self.reader = None

            if not self._running:
                break

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)

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
        if "!" not in line or "@" not in line:
            return

        partes = line.split("!")
        if len(partes) > 1 and partes[0].startswith(":"):
            usuario = partes[0][1:].lower()

            if " JOIN #" in line:
                await self._handle_event(usuario, "JOIN")
            elif " PART #" in line:
                await self._handle_event(usuario, "PART")

    async def _get_user_role(
        self,
        usuario: twitchio.PartialUser | None,
        broadcaster: twitchio.PartialUser | None,
    ) -> str:
        """Determina el rol del usuario como string limpio (sin markup Rich)."""
        #! Teoricamente, nunca sucedera
        if usuario is None or broadcaster is None:
            return "Desconocido"

        if usuario.id == broadcaster.id:
            return "Broadcaster"

        if usuario.id == self.bot.bot_id:
            return "Bot"

        if await self.bot.user_repo.is_user_bot(usuario.id):
            return "Bot"

        follow = await broadcaster.fetch_followers(user=usuario, first=1)
        async for event in follow.followers:
            return event.followed_at.strftime("%d/%m/%y")

        return "Visita"

    async def _handle_event(self, usuario: str, action: str) -> None:
        if usuario == self.bot_username:
            return

        user_id = await self.bot.user_repo.get_user_id_by_name(usuario)
        display_name = usuario

        twitch_user = None
        try:
            twitch_user = await self.bot.fetch_user(login=usuario)
            if twitch_user:
                display_name = twitch_user.display_name
                if not user_id and action == "JOIN":
                    user_id = str(twitch_user.id)
                    await self.bot.user_repo.upsert_user(
                        user_id,
                        twitch_user.name,
                        display_name,
                    )
        except Exception as e:
            LOGGER.error("Error al buscar fetch_user para %s: %s", usuario, e)

        nickname = None
        if user_id:
            nickname = await self.bot.user_repo.get_user_nickname(user_id)

        r, g, b = get_chatter_rgb(None, usuario)

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
            role = await self._get_user_role(twitch_user, self.broadcaster)
        except Exception as e:
            LOGGER.error("Error al obtener rol para %s: %s", usuario, e)
            role = "Desconocido"

        if action == "JOIN":
            is_bot = False
            is_mod = False
            is_vip = False
            is_sub = False
            sub_tier = None
            if twitch_user:
                is_bot = (twitch_user.id == self.bot.bot_id) or (
                    await self.bot.user_repo.is_user_bot(str(twitch_user.id))
                )
            elif user_id:
                is_bot = await self.bot.user_repo.is_user_bot(user_id)

            if user_id:
                roles = await self.bot.user_repo.get_user_roles(
                    user_id, self.bot.owner_id
                )
                if roles:
                    is_mod = roles["is_moderator"]
                    is_vip = roles["is_vip"]
                    is_sub = roles["is_subscriber"]
                    sub_tier = roles.get("sub_tier")

            join_event = UserJoinEvent(
                timestamp=datetime.now().isoformat(),
                user_id=user_id,
                username=usuario,
                display_name=display_name,
                nickname=nickname,
                color_rgb=(r, g, b),
                role=role,
                is_bot=is_bot,
                is_moderator=is_mod,
                is_vip=is_vip,
                is_subscriber=is_sub,
                sub_tier=sub_tier,
            )
            self.connected_users[usuario] = join_event
            await self.bot.event_bus.emit(join_event)
        else:
            self.connected_users.pop(usuario, None)
            await self.bot.event_bus.emit(
                UserPartEvent(
                    timestamp=datetime.now().isoformat(),
                    user_id=user_id,
                    username=usuario,
                    display_name=display_name,
                    nickname=nickname,
                    color_rgb=(r, g, b),
                    role=role,
                )
            )
