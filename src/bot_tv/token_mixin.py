"""Mixin para persistir tokens OAuth automáticamente.

Evita duplicar la lógica de add_token entre Bot y SetupBot.
Ambos heredan de este mixin para guardar tokens en la DB
cada vez que se agrega uno nuevo.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import twitchio

if TYPE_CHECKING:
    import asqlite

LOGGER = logging.getLogger(__name__)


class TokenPersistMixin:
    """Mixin que persiste tokens en la base de datos al añadirlos.

    La clase que use este mixin DEBE tener un atributo `token_database`
    de tipo `asqlite.Pool` y heredar de una clase que tenga `add_token`.
    """

    token_database: asqlite.Pool

    async def add_token(
        self, token: str, refresh: str
    ) -> twitchio.authentication.ValidateTokenPayload:
        """Añade y persiste un token de acceso en la base de datos."""
        from bot_tv.token_database import save_token

        # pyrefly: ignore [missing-attribute]
        resp: twitchio.authentication.ValidateTokenPayload = await super().add_token(
            token, refresh
        )
        if resp.user_id and resp.login:
            await save_token(
                self.token_database, resp.user_id, resp.login, token, refresh
            )
            LOGGER.info("Token almacenado para: %s (ID: %s)", resp.login, resp.user_id)
        return resp
