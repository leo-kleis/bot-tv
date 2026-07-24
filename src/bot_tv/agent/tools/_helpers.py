from __future__ import annotations

from typing import TYPE_CHECKING

from bot_tv.utils.formatting import format_date

if TYPE_CHECKING:
    from bot_tv.bot import Bot


async def get_broadcaster_id(bot: Bot) -> str:
    """Obtiene el ID del broadcaster de forma segura (OWNER_ID o primer canal)."""
    if bot.owner_id and bot.owner_id.strip():
        return bot.owner_id.strip()
    channels = await bot.get_channels()
    if channels:
        return channels[0]["user_id"]
    return ""


def format_user_details(
    username: str,
    display_name: str | None,
    nickname: str | None,
    followed_at: str | None,
    unfollowed_at: str | None,
) -> str:
    """Formatea la información detallada de un usuario y su estado de seguimiento."""
    name = display_name or username
    name_str = f"{name} ({nickname})" if nickname else name

    if followed_at:
        if unfollowed_at:
            return (
                f"{name_str} - No es seguidor (Siguió el: "
                f"{format_date(followed_at)} - Dejó de seguir el: "
                f"{format_date(unfollowed_at)})"
            )
        return f"{name_str} - Seguidor desde: {format_date(followed_at)}"
    return f"{name_str} - No es seguidor"
