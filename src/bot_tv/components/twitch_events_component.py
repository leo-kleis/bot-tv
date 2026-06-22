from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import twitchio
from twitchio.ext import commands

from bot_tv.events import (
    TwitchBanEvent,
    TwitchChannelPointsRedeemEvent,
    TwitchChatClearEvent,
    TwitchChatClearUserEvent,
    TwitchCheerEvent,
    TwitchMessageDeleteEvent,
    TwitchPredictionBeginEvent,
    TwitchPredictionEndEvent,
    TwitchPredictionLockEvent,
    TwitchPredictionProgressEvent,
    TwitchRaidEvent,
    TwitchSubscribeEvent,
    TwitchSubscriptionGiftEvent,
    TwitchSubscriptionMessageEvent,
    TwitchUnbanEvent,
)

if TYPE_CHECKING:
    from bot_tv.bot import Bot

LOGGER = logging.getLogger(__name__)


class TwitchEventsComponent(commands.Component):
    """Componente que escucha eventos y alertas de Twitch (EventSub) y los publica."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    # ── Raid ────────────────────────────────────────────────────────────────

    @commands.Component.listener()
    async def event_raid(self, payload: twitchio.models.ChannelRaid) -> None:
        """Se ejecuta cuando el canal recibe una raid."""
        from_user = payload.from_broadcaster
        from_username = from_user.name or ""
        from_display_name = from_user.display_name or from_username or "Alguien"

        await self.bot.event_bus.emit(
            TwitchRaidEvent(
                from_username=from_username,
                from_display_name=from_display_name,
                viewer_count=payload.viewer_count,
            )
        )

    # ── Suscripciones ───────────────────────────────────────────────────────

    @commands.Component.listener()
    async def event_subscription(
        self, payload: twitchio.models.ChannelSubscribe
    ) -> None:
        """Se ejecuta cuando un usuario se suscribe al canal."""
        username = payload.user.name or ""
        display_name = payload.user.display_name or username or "Alguien"

        await self.bot.event_bus.emit(
            TwitchSubscribeEvent(
                username=username,
                display_name=display_name,
                tier=payload.tier or "1000",
                is_gift=payload.gift,
            )
        )

    @commands.Component.listener()
    async def event_subscription_gift(
        self, payload: twitchio.models.ChannelSubscriptionGift
    ) -> None:
        """Se ejecuta cuando se regalan suscripciones en el canal."""
        user_name = payload.user.name if payload.user else None
        display_name = payload.user.display_name if payload.user else "Regalo Anónimo"
        await self.bot.event_bus.emit(
            TwitchSubscriptionGiftEvent(
                username=user_name,
                display_name=display_name,
                tier=payload.tier or "1000",
                total=payload.total or 1,
                cumulative_total=payload.cumulative_total,
                is_anonymous=payload.anonymous,
            )
        )

    @commands.Component.listener()
    async def event_subscription_message(
        self, payload: twitchio.models.ChannelSubscriptionMessage
    ) -> None:
        """Se ejecuta cuando un usuario envía su mensaje de resub al chat."""
        username = payload.user.name or ""
        display_name = payload.user.display_name or username or "Alguien"
        # pyrefly: ignore [missing-attribute]
        msg = payload.message.text if payload.message else ""

        await self.bot.event_bus.emit(
            TwitchSubscriptionMessageEvent(
                username=username,
                display_name=display_name,
                tier=payload.tier or "1000",
                cumulative_months=payload.cumulative_months or 1,
                streak_months=payload.streak_months,
                message=msg or "",
            )
        )

    # ── Cheer (Bits) ────────────────────────────────────────────────────────

    @commands.Component.listener()
    async def event_cheer(self, payload: twitchio.models.ChannelCheer) -> None:
        """Se ejecuta cuando un usuario hace un cheer con bits."""
        user_name = payload.user.name if payload.user else None
        display_name = payload.user.display_name if payload.user else "Anónimo"
        await self.bot.event_bus.emit(
            TwitchCheerEvent(
                username=user_name,
                display_name=display_name,
                bits=payload.bits or 0,
                message=payload.message or "",
                is_anonymous=payload.anonymous,
            )
        )

    # ── Puntos de Canal ─────────────────────────────────────────────────────

    @commands.Component.listener()
    async def event_custom_redemption_add(
        self, payload: twitchio.models.ChannelPointsRedemptionAdd
    ) -> None:
        """Se ejecuta cuando un usuario canjea una recompensa."""
        username = payload.user.name or ""
        display_name = payload.user.display_name or username or "Alguien"

        await self.bot.event_bus.emit(
            TwitchChannelPointsRedeemEvent(
                username=username,
                display_name=display_name,
                reward_title=payload.reward.title or "Recompensa",
                reward_cost=payload.reward.cost or 0,
                user_input=payload.user_input or "",
            )
        )

    # ── Predicciones ────────────────────────────────────────────────────────

    @commands.Component.listener()
    async def event_prediction_begin(
        self, payload: twitchio.models.ChannelPredictionBegin
    ) -> None:
        """Se ejecuta cuando inicia una predicción."""
        outcomes = [o.title for o in payload.outcomes]
        locks_at = (
            payload.locks_at.isoformat()
            if hasattr(payload.locks_at, "isoformat")
            else str(payload.locks_at)
        )

        await self.bot.event_bus.emit(
            TwitchPredictionBeginEvent(
                title=payload.title,
                outcomes=outcomes,
                locks_at=locks_at,
            )
        )

    @commands.Component.listener()
    async def event_prediction_progress(
        self, payload: twitchio.models.ChannelPredictionProgress
    ) -> None:
        """Se ejecuta cuando hay progreso en una predicción."""
        votes = [
            (o.title, o.channel_points or 0, o.users or 0) for o in payload.outcomes
        ]
        locks_at = (
            payload.locks_at.isoformat()
            if hasattr(payload.locks_at, "isoformat")
            else str(payload.locks_at)
        )

        await self.bot.event_bus.emit(
            TwitchPredictionProgressEvent(
                title=payload.title,
                outcomes_votes=votes,
                locks_at=locks_at,
            )
        )

    @commands.Component.listener()
    async def event_prediction_lock(
        self, payload: twitchio.models.ChannelPredictionLock
    ) -> None:
        """Se ejecuta cuando se cierran las apuestas de la predicción."""
        await self.bot.event_bus.emit(
            TwitchPredictionLockEvent(
                title=payload.title,
            )
        )

    @commands.Component.listener()
    async def event_prediction_end(
        self, payload: twitchio.models.ChannelPredictionEnd
    ) -> None:
        """Se ejecuta cuando finaliza una predicción."""
        winning_title = None
        winning_id = getattr(payload, "winning_outcome_id", None)
        if winning_id:
            for outcome in payload.outcomes:
                if outcome.id == winning_id:
                    winning_title = outcome.title
                    break

        await self.bot.event_bus.emit(
            TwitchPredictionEndEvent(
                title=payload.title,
                status=payload.status or "resolved",
                winning_outcome_title=winning_title,
            )
        )

    # ── Moderación ──────────────────────────────────────────────────────────

    @commands.Component.listener()
    async def event_ban(self, payload: twitchio.models.ChannelBan) -> None:
        """Se ejecuta cuando un usuario es baneado o puesto en timeout."""
        username = payload.user.name or ""
        display_name = payload.user.display_name or username or "Usuario"
        mod_name = (
            payload.moderator.display_name or payload.moderator.name or "Moderador"
        )
        duration = None
        if payload.ends_at and payload.banned_at:
            try:
                duration = int((payload.ends_at - payload.banned_at).total_seconds())
            except Exception:
                duration = None

        await self.bot.event_bus.emit(
            TwitchBanEvent(
                username=username,
                display_name=display_name,
                moderator_name=mod_name,
                reason=payload.reason,
                permanent=payload.permanent,
                duration_seconds=duration,
            )
        )

    @commands.Component.listener()
    async def event_unban(self, payload: twitchio.models.ChannelUnban) -> None:
        """Se ejecuta cuando un usuario es desbaneado."""
        username = payload.user.name or ""
        display_name = payload.user.display_name or username or "Usuario"
        mod_name = (
            payload.moderator.display_name or payload.moderator.name or "Moderador"
        )

        await self.bot.event_bus.emit(
            TwitchUnbanEvent(
                username=username,
                display_name=display_name,
                moderator_name=mod_name,
            )
        )

    @commands.Component.listener()
    async def event_chat_clear(self, payload: twitchio.models.ChannelChatClear) -> None:
        """Se ejecuta cuando un moderador limpia el chat entero (/clear)."""
        await self.bot.event_bus.emit(TwitchChatClearEvent())

    @commands.Component.listener()
    async def event_chat_clear_user(
        self, payload: twitchio.models.ChannelChatClearUserMessages
    ) -> None:
        """Se ejecuta cuando se purgan los mensajes de un usuario en el chat."""
        username = payload.user.name or ""
        display_name = payload.user.display_name or username or "Usuario"

        await self.bot.event_bus.emit(
            TwitchChatClearUserEvent(
                username=username,
                display_name=display_name,
            )
        )

    @commands.Component.listener()
    async def event_message_delete(
        self, payload: twitchio.models.ChatMessageDelete
    ) -> None:
        """Se ejecuta cuando un moderador borra un mensaje individual."""
        username = payload.user.name or ""
        display_name = payload.user.display_name or username or "Usuario"

        await self.bot.event_bus.emit(
            TwitchMessageDeleteEvent(
                username=username,
                display_name=display_name,
                message_text=f"Mensaje ID: {payload.message_id}",
            )
        )
