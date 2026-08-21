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
        self.parted_users: dict[str, UserPartEvent] = {}
        self._tasks: set[asyncio.Task[None]] = set()
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

    def _get_user_role_cached(
        self, user_id: str | None, broadcaster_id: str | int
    ) -> str:
        """Determina el rol del usuario instantáneamente desde UserMemoryCache."""
        if not user_id:
            return "Visita"

        uid_str = user_id
        bid_str = str(broadcaster_id)

        if uid_str == bid_str:
            return "Broadcaster"

        if uid_str == str(self.bot.bot_id):
            return "Bot"

        if self.bot.user_cache.is_user_bot(uid_str):
            return "Bot"

        roles = self.bot.user_cache.get_user_roles(uid_str, bid_str)
        if roles and roles.get("followed_at") and not roles.get("unfollowed_at"):
            fat = roles.get("followed_at")
            try:
                clean = fat.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean).astimezone()
                return dt.strftime("%d/%m/%y")
            except Exception:
                return "Visita"

        return "Visita"

    async def _resolve_and_cache_new_user(self, usuario: str) -> None:
        """Resuelve en background datos para usuarios no presentes en caché."""
        cache = self.bot.user_cache
        try:
            twitch_user = await self.bot.fetch_user(login=usuario)
            if twitch_user:
                uid = str(twitch_user.id)
                display_name = twitch_user.display_name
                await self.bot.user_repo.upsert_user(
                    uid,
                    twitch_user.name,
                    display_name,
                    cache=cache,
                )
        except Exception as e:
            LOGGER.debug(
                "No se pudo resolver usuario nuevo %s en background: %s", usuario, e
            )

    async def _handle_event(self, usuario: str, action: str) -> None:
        if usuario == self.bot_username:
            return

        cache = self.bot.user_cache
        user_id = cache.get_user_id_by_name(usuario)
        user_data = cache.get_user(user_id) if user_id else None

        display_name = (user_data.get("display_name") if user_data else None) or usuario
        nickname = user_data.get("nickname") if user_data else None
        r, g, b = get_chatter_rgb(None, usuario)
        role = self._get_user_role_cached(user_id, self.bot.owner_id)

        is_bot = (user_id == str(self.bot.bot_id)) or (
            cache.is_user_bot(user_id) if user_id else False
        )
        is_mod = False
        is_vip = False
        is_sub = False
        sub_tier = None

        if user_id:
            roles = cache.get_user_roles(user_id, str(self.bot.owner_id))
            if roles:
                is_mod = bool(roles.get("is_moderator", False))
                is_vip = bool(roles.get("is_vip", False))
                is_sub = bool(roles.get("is_subscriber", False))
                sub_tier = roles.get("sub_tier")
        elif action == "JOIN":
            # Si el usuario no estaba en caché, resolverlo en segundo plano
            task = asyncio.create_task(self._resolve_and_cache_new_user(usuario))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        user_key = user_id or usuario

        if action == "JOIN":
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
            self.connected_users[user_key] = join_event
            self.parted_users.pop(user_key, None)
            if user_id:
                self.parted_users.pop(user_id, None)
            self.parted_users.pop(usuario, None)

            await self.bot.event_bus.emit(join_event)
        else:
            part_event = UserPartEvent(
                timestamp=datetime.now().isoformat(),
                user_id=user_id,
                username=usuario,
                display_name=display_name,
                nickname=nickname,
                color_rgb=(r, g, b),
                role=role,
            )
            self.connected_users.pop(user_key, None)
            if user_id:
                self.connected_users.pop(user_id, None)
            self.connected_users.pop(usuario, None)
            self.parted_users[user_key] = part_event

            await self.bot.event_bus.emit(part_event)
