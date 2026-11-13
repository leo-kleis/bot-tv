from __future__ import annotations

from typing import TYPE_CHECKING

from bot_tv.agent.tools._helpers import AgentToolFn
from bot_tv.agent.tools.channel_users import build_channel_user_tools
from bot_tv.agent.tools.chat import build_chat_tools
from bot_tv.agent.tools.stream import build_stream_tools
from bot_tv.agent.tools.users import build_user_tools

if TYPE_CHECKING:
    from bot_tv.bot import Bot


def build_agent_tools(bot: Bot) -> list[AgentToolFn]:
    """Construye y consolida todas las herramientas del agente divididas
    por dominios.
    """
    tools: list[AgentToolFn] = []
    tools.extend(build_stream_tools(bot))
    tools.extend(build_channel_user_tools(bot))
    tools.extend(build_user_tools(bot))
    tools.extend(build_chat_tools(bot))
    return tools


__all__ = ["build_agent_tools"]
