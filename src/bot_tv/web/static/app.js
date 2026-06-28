import { html, render, useReducer } from 'preact-setup';
import { App } from '/static/components/App.js';
import { useWebSocket } from '/static/hooks/useWebSocket.js';

// ── Registro del service worker ──────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

// ── Constantes ───────────────────────────────────────────────────────────────
const MAX_CHAT = 300;

// ── Estado inicial ───────────────────────────────────────────────────────────
function makeInitialState() {
  return {
    connected: false,
    historyLoaded: false,
    initialLoad: true,
    stream: {
      online: false,
      broadcasterName: '',
      title: '',
      category: '',
      viewerCount: null,
      viewerDiff: null,
      startedAt: null,
    },
    chatMessages: [],
    ircUsers: new Map(), // username → {display_name, nickname, color_rgb, role}
    ircEvents: [], // log de JOIN/PART para mostrar en historial si hace falta
    followers: {
      lastSync: null, // FollowerSyncEvent más reciente
      progress: null, // FollowerProgressEvent en curso
    },
    clips: [],
    agentConversations: [],
    exited: false,
    toasts: [],
  };
}

// ── Reducer ───────────────────────────────────────────────────────────────────
function reducer(state, action) {
  switch (action.type) {
    case 'WS_CONNECTED':
      return { ...state, connected: true, exited: false, initialLoad: false };

    case 'WS_DISCONNECTED':
      return { ...state, connected: false, historyLoaded: false, initialLoad: false };

    case 'HISTORY_END':
      return { ...state, historyLoaded: true };

    case 'chat_message': {
      const msgs = [...state.chatMessages, action.data];
      return { ...state, chatMessages: msgs.length > MAX_CHAT ? msgs.slice(-MAX_CHAT) : msgs };
    }

    case 'user_join': {
      const next = new Map(state.ircUsers);
      next.set(action.data.username, action.data);
      return { ...state, ircUsers: next };
    }

    case 'user_part': {
      const next = new Map(state.ircUsers);
      next.delete(action.data.username);
      return { ...state, ircUsers: next };
    }

    case 'stream_online':
      return {
        ...state,
        stream: {
          ...state.stream,
          online: true,
          broadcasterName: action.data.broadcaster_name,
          title: action.data.title,
          category: action.data.category,
          startedAt: action.data.started_at,
        },
      };

    case 'stream_offline':
      return {
        ...state,
        stream: {
          ...state.stream,
          online: false,
          viewerCount: null,
          viewerDiff: null,
          startedAt: null,
        },
      };

    case 'viewer_update':
      return {
        ...state,
        stream: {
          ...state.stream,
          viewerCount: action.data.count,
          viewerDiff: action.data.diff,
        },
      };

    case 'follower_sync':
      return { ...state, followers: { ...state.followers, lastSync: action.data, progress: null } };

    case 'follower_progress':
      return { ...state, followers: { ...state.followers, progress: action.data } };

    case 'clip_created': {
      const clips = [action.data, ...state.clips].slice(0, 20);
      return { ...state, clips };
    }

    case 'agent_question_pending': {
      return {
        ...state,
        agentConversations: [
          ...state.agentConversations,
          {
            timestamp: action.data.timestamp,
            question: action.data.question,
            response: null,
            model: null,
          },
        ],
      };
    }

    case 'agent_response': {
      const list = [...state.agentConversations];
      const pendingIdx = list.findLastIndex(
        c => c.question === action.data.question && c.response === null
      );
      if (pendingIdx !== -1) {
        list[pendingIdx] = action.data;
      } else {
        if (!list.some(c => c.timestamp === action.data.timestamp)) {
          list.push(action.data);
        }
      }
      return { ...state, agentConversations: list };
    }

    case 'BOT_EXITED':
      return { ...state, exited: true };

    case 'twitch_raid':
    case 'twitch_subscribe':
    case 'twitch_sub_gift':
    case 'twitch_sub_message':
    case 'twitch_cheer':
    case 'twitch_points_redeem':
    case 'prediction_begin':
    case 'prediction_lock':
    case 'prediction_end':
    case 'twitch_ban':
    case 'twitch_unban':
    case 'twitch_chat_clear':
    case 'twitch_chat_clear_user':
    case 'twitch_message_delete': {
      const systemMsg = {
        isSystem: true,
        type: action.type,
        timestamp: action.data.timestamp || new Date().toISOString(),
        data: action.data,
      };
      const msgs = [...state.chatMessages, systemMsg];
      return { ...state, chatMessages: msgs.length > MAX_CHAT ? msgs.slice(-MAX_CHAT) : msgs };
    }

    case 'prediction_progress':
      // Ignorar del feed de chat para evitar spam, o manejar si es necesario.
      return state;

    case 'ADD_TOAST':
      return { ...state, toasts: [...state.toasts, action.toast] };

    case 'REMOVE_TOAST':
      return { ...state, toasts: state.toasts.filter(t => t.id !== action.id) };

    default:
      return state;
  }
}

// ── Root Component ────────────────────────────────────────────────────────────
function Root() {
  const [state, dispatch] = useReducer(reducer, null, makeInitialState);
  const { triggerReconnect } = useWebSocket(dispatch);

  return html`<${App} state=${state} dispatch=${dispatch} onReconnect=${triggerReconnect} />`;
}

// ── Mount ─────────────────────────────────────────────────────────────────────
render(html`<${Root} />`, document.getElementById('app'));
