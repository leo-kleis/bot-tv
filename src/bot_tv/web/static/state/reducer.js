import { MAX_TOASTS } from './constants.js';
import { appendSystemMessage } from './chatUtils.js';
import {
  handleAgentQuestionPending,
  handleAgentResponse,
  handleChatMessage,
  handleClipCreated,
  handleFollowerSync,
  handleStreamOffline,
  handleStreamOnline,
  handleStreamUpdate,
  handleViewerUpdate,
} from './eventHandlers.js';
import {
  handleTwitchFollow,
  handleUserJoin,
  handleUserNicknameUpdated,
  handleUserPart,
  handleUserRoleUpdated,
} from './ircHandlers.js';

/** @typedef {import('./types.js').AgentConversation} AgentConversation */
/** @typedef {import('./types.js').AppAction} AppAction */
/** @typedef {import('./types.js').AppState} AppState */
/** @typedef {import('./types.js').ChatMessage} ChatMessage */
/** @typedef {import('./types.js').ClipData} ClipData */
/** @typedef {import('./types.js').FollowerProgressData} FollowerProgressData */
/** @typedef {import('./types.js').FollowerSyncData} FollowerSyncData */
/** @typedef {import('./types.js').IrcUser} IrcUser */
/** @typedef {import('./types.js').SystemEventPayload} SystemEventPayload */

const SYSTEM_CHAT_EVENT_TYPES = new Set([
  'twitch_raid',
  'twitch_subscribe',
  'twitch_sub_gift',
  'twitch_sub_message',
  'twitch_cheer',
  'twitch_points_redeem',
  'prediction_begin',
  'prediction_lock',
  'prediction_end',
  'twitch_ban',
  'twitch_unban',
  'twitch_chat_clear',
  'twitch_chat_clear_user',
  'twitch_message_delete',
]);

/**
 * Reducer principal del estado de la aplicación.
 * @param {AppState} state
 * @param {AppAction} action
 * @returns {AppState}
 */
export function reducer(state, action) {
  switch (action.type) {
    case 'WS_BATCH':
      return Array.isArray(action.events) ? action.events.reduce(reducer, state) : state;

    case 'WS_CONNECTED':
      if (state.connected && !state.exited && !state.initialLoad) return state;
      return { ...state, connected: true, exited: false, initialLoad: false };

    case 'WS_DISCONNECTED':
      if (!state.connected && !state.historyLoaded && !state.initialLoad) return state;
      return { ...state, connected: false, historyLoaded: false, initialLoad: false };

    case 'HISTORY_END':
    case 'history_end':
      if (state.historyLoaded) return state;
      return { ...state, historyLoaded: true };

    case 'irc_status': {
      const nextConnected = Boolean(action.data?.connected);
      if (state.ircConnected === nextConnected) return state;
      return { ...state, ircConnected: nextConnected };
    }

    case 'chat_message':
      return action.data
        ? handleChatMessage(state, /** @type {ChatMessage} */ (action.data))
        : state;

    case 'user_join':
      return action.data ? handleUserJoin(state, /** @type {IrcUser} */ (action.data)) : state;

    case 'user_part':
      return action.data ? handleUserPart(state, /** @type {IrcUser} */ (action.data)) : state;

    case 'stream_online':
      return action.data
        ? handleStreamOnline(
            state,
            /** @type {{ broadcaster_name: string, title: string, category: string, started_at: string }} */ (
              action.data
            )
          )
        : state;

    case 'stream_offline':
      return action.data
        ? handleStreamOffline(
            state,
            /** @type {{ broadcaster_name?: string, title?: string, category?: string }} */ (
              action.data
            )
          )
        : state;

    case 'stream_update':
      return action.data
        ? handleStreamUpdate(
            state,
            /** @type {{ broadcaster_name?: string, title?: string, category?: string }} */ (
              action.data
            )
          )
        : state;

    case 'viewer_update':
      return action.data
        ? handleViewerUpdate(
            state,
            /** @type {{ count: number | null, diff: number | null }} */ (action.data)
          )
        : state;

    case 'follower_sync':
      return action.data
        ? handleFollowerSync(state, /** @type {FollowerSyncData} */ (action.data))
        : state;

    case 'CLEAR_UNREAD_FOLLOWERS':
      if (!state.followers.unreadCount) return state;
      return { ...state, followers: { ...state.followers, unreadCount: 0 } };

    case 'follower_progress':
      return {
        ...state,
        followers: {
          ...state.followers,
          progress: /** @type {FollowerProgressData | null} */ (action.data || null),
        },
      };

    case 'clip_created':
      return action.data ? handleClipCreated(state, /** @type {ClipData} */ (action.data)) : state;

    case 'agent_question_pending':
      return action.data
        ? handleAgentQuestionPending(
            state,
            /** @type {{ timestamp: string, question: string }} */ (action.data)
          )
        : state;

    case 'agent_response':
      return action.data
        ? handleAgentResponse(state, /** @type {AgentConversation} */ (action.data))
        : state;

    case 'agent_clear_history':
      if (state.agentConversations.length === 0) return state;
      return { ...state, agentConversations: [] };

    case 'BOT_EXITED':
      if (state.exited) return state;
      return { ...state, exited: true };

    case 'user_nickname_updated':
      return action.data
        ? handleUserNicknameUpdated(
            state,
            /** @type {{ user_id?: string, username?: string, nickname?: string | null, timestamp?: string, display_name?: string }} */ (
              action.data
            )
          )
        : state;

    case 'user_role_updated':
      return action.data
        ? handleUserRoleUpdated(state, /** @type {SystemEventPayload} */ (action.data))
        : state;

    case 'twitch_follow':
      return action.data
        ? handleTwitchFollow(
            state,
            /** @type {{ user_id?: string, username?: string, display_name?: string, role?: string, timestamp?: string }} */ (
              action.data
            )
          )
        : state;

    case 'prediction_progress':
      return state;

    case 'ADD_TOAST':
      if (!action.toast) return state;
      return { ...state, toasts: [...state.toasts, action.toast].slice(-MAX_TOASTS) };

    case 'REMOVE_TOAST': {
      const filtered = state.toasts.filter(t => t.id !== action.id);
      if (filtered.length === state.toasts.length) return state;
      return { ...state, toasts: filtered };
    }

    default: {
      if (SYSTEM_CHAT_EVENT_TYPES.has(action.type) && action.data) {
        const nextMessages = appendSystemMessage(
          state.chatMessages,
          action.type,
          /** @type {SystemEventPayload} */ (action.data)
        );
        if (nextMessages === state.chatMessages) return state;
        return { ...state, chatMessages: nextMessages };
      }
      return state;
    }
  }
}
