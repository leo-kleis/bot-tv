from __future__ import annotations

import logging

import asyncpg
import twitchio
from twitchio import eventsub

from bot_tv.database.repositories.base import BaseRepository
from bot_tv.utils.env import BOT_ID
from bot_tv.utils.security import get_fernet

LOGGER = logging.getLogger(__name__)


class TokenRepository(BaseRepository):
    """Repositorio para gestionar las operaciones sobre la tabla tokens (encriptada)."""

    async def save_token(
        self, user_id: str, username: str, token: str, refresh: str
    ) -> None:
        """Encripta e inserta o actualiza un token en la base de datos."""
        fernet = get_fernet()
        encrypted_token = fernet.encrypt(token.encode()).decode()
        encrypted_refresh = fernet.encrypt(refresh.encode()).decode()

        query = """
            INSERT INTO tokens (user_id, username, token, refresh)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id)
            DO UPDATE SET username = EXCLUDED.username,
                          token    = EXCLUDED.token,
                          refresh  = EXCLUDED.refresh
        """
        async with self._db.acquire() as conn:
            await conn.execute(
                query, user_id, username, encrypted_token, encrypted_refresh
            )

    @staticmethod
    def get_user_subscriptions(
        user_id: str, bot_id: str
    ) -> list[eventsub.SubscriptionPayload]:
        """Retorna las suscripciones de EventSub de un broadcaster."""
        return [
            eventsub.ChatMessageSubscription(
                broadcaster_user_id=user_id, user_id=bot_id
            ),
            eventsub.StreamOnlineSubscription(broadcaster_user_id=user_id),
            eventsub.StreamOfflineSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelRaidSubscription(to_broadcaster_user_id=user_id),
            eventsub.ChannelSubscribeSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelSubscribeMessageSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelSubscriptionGiftSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelCheerSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelPointsRedeemAddSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelPredictionBeginSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelPredictionProgressSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelPredictionLockSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelPredictionEndSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelBanSubscription(broadcaster_user_id=user_id),
            eventsub.ChannelUnbanSubscription(broadcaster_user_id=user_id),
            eventsub.ChatClearSubscription(broadcaster_user_id=user_id, user_id=bot_id),
            eventsub.ChatClearUserMessagesSubscription(
                broadcaster_user_id=user_id, user_id=bot_id
            ),
            eventsub.ChatMessageDeleteSubscription(
                broadcaster_user_id=user_id, user_id=bot_id
            ),
        ]

    async def load_tokens_and_subscriptions(
        self,
    ) -> tuple[list[tuple[str, str]], list[eventsub.SubscriptionPayload]]:
        """Carga los tokens de la DB, los desencripta y genera suscripciones."""
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch("SELECT * FROM tokens")

        fernet = get_fernet()
        tokens: list[tuple[str, str]] = []
        subs: list[eventsub.SubscriptionPayload] = []

        for row in rows:
            try:
                dec_token = fernet.decrypt(row["token"].encode()).decode()
                dec_refresh = fernet.decrypt(row["refresh"].encode()).decode()
            except Exception as e:
                LOGGER.error(
                    "Error al desencriptar token/refresh para %s (ID: %s): %s",
                    row["username"],
                    row["user_id"],
                    e,
                )
                continue

            tokens.append((dec_token, dec_refresh))

            if row["user_id"] != BOT_ID:
                subs.extend(
                    TokenRepository.get_user_subscriptions(row["user_id"], BOT_ID)
                )

        return tokens, subs

    async def get_all_tokens_metadata(self) -> list[dict[str, str]]:
        """Obtiene todos los registros de tokens desencriptados con sus metadatos."""
        async with self._db.acquire() as conn:
            rows: list[asyncpg.Record] = await conn.fetch("SELECT * FROM tokens")

        fernet = get_fernet()
        results: list[dict[str, str]] = []

        for row in rows:
            try:
                dec_token = fernet.decrypt(row["token"].encode()).decode()
                dec_refresh = fernet.decrypt(row["refresh"].encode()).decode()
                results.append(
                    {
                        "user_id": row["user_id"],
                        "username": row["username"],
                        "token": dec_token,
                        "refresh": dec_refresh,
                    }
                )
            except Exception as e:
                LOGGER.error(
                    "Error al desencriptar metadatos de token para %s: %s",
                    row["username"],
                    e,
                )
        return results


class TokenPersistMixin:
    """Mixin que persiste tokens encriptados en la base de datos al añadirlos.

    La clase que use este mixin DEBE tener un atributo `token_repo`
    de tipo `TokenRepository` y heredar de una clase que tenga `add_token`.
    """

    token_repo: TokenRepository

    async def add_token(
        self, token: str, refresh: str
    ) -> twitchio.authentication.ValidateTokenPayload:
        """Añade y persiste un token de acceso de forma encriptada."""
        # pyrefly: ignore [missing-attribute]
        resp: twitchio.authentication.ValidateTokenPayload = await super().add_token(
            token, refresh
        )
        if resp.user_id and resp.login:
            await self.token_repo.save_token(resp.user_id, resp.login, token, refresh)
            LOGGER.info(
                "Token encriptado y almacenado para: %s (ID: %s)",
                resp.login,
                resp.user_id,
            )
        return resp
