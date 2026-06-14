from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from bot_tv.agent.tools.chat import build_chat_tools
from bot_tv.agent.tools.followers import build_follower_tools
from bot_tv.agent.tools.stream import build_stream_tools
from bot_tv.agent.tools.users import build_user_tools

if TYPE_CHECKING:
    from bot_tv.bot import Bot


def build_agent_tools(bot: Bot) -> list[Callable[..., Any]]:
    """Construye y consolida todas las herramientas del agente divididas
    por dominios.
    """
    tools: list[Callable[..., Any]] = []
    tools.extend(build_stream_tools(bot))
    tools.extend(build_follower_tools(bot))
    tools.extend(build_user_tools(bot))
    tools.extend(build_chat_tools(bot))
    return tools


__all__ = ["build_agent_tools"]
