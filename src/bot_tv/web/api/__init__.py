"""Paquete REST API: endpoints modularizados para acciones del bot desde la web.

Reexporta todos los endpoints de forma limpia y segura para preservar la
compatibilidad retroactiva.
"""

from __future__ import annotations

from bot_tv.web.api.agent import (
    endpoint_clear_agent_chat,
    endpoint_get_models,
    endpoint_get_rpm,
    endpoint_set_context_limit,
    endpoint_switch_model,
    endpoint_talk,
)
from bot_tv.web.api.chat import (
    endpoint_get_chat_accounts,
    endpoint_get_ffz_emotes,
    endpoint_send_chat_message,
)
from bot_tv.web.api.helpers import _err, _ok, _parse_body
from bot_tv.web.api.moderation import (
    endpoint_moderation_ban,
    endpoint_moderation_delete_message,
    endpoint_moderation_purge,
    endpoint_moderation_unban,
)
from bot_tv.web.api.stream import (
    endpoint_search_categories,
    endpoint_update_stream_info,
)
from bot_tv.web.api.system import (
    endpoint_create_clip,
    endpoint_exit,
)
from bot_tv.web.api.users import (
    endpoint_get_avatar,
    endpoint_list_users,
    endpoint_search_users,
    endpoint_set_nickname,
    endpoint_sync_followers,
    endpoint_sync_user_roles,
    endpoint_update_user_roles,
    endpoint_user_messages,
)

__all__ = [
    "_err",
    "_ok",
    "_parse_body",
    "endpoint_clear_agent_chat",
    "endpoint_create_clip",
    "endpoint_exit",
    "endpoint_get_avatar",
    "endpoint_get_chat_accounts",
    "endpoint_get_ffz_emotes",
    "endpoint_get_models",
    "endpoint_get_rpm",
    "endpoint_list_users",
    "endpoint_moderation_ban",
    "endpoint_moderation_delete_message",
    "endpoint_moderation_purge",
    "endpoint_moderation_unban",
    "endpoint_search_categories",
    "endpoint_search_users",
    "endpoint_send_chat_message",
    "endpoint_set_context_limit",
    "endpoint_set_nickname",
    "endpoint_switch_model",
    "endpoint_sync_followers",
    "endpoint_sync_user_roles",
    "endpoint_talk",
    "endpoint_update_stream_info",
    "endpoint_update_user_roles",
    "endpoint_user_messages",
]
