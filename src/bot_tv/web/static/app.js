import { html, render, useReducer } from 'preact-setup';
import { App } from '/static/components/App.js';
import { useWebSocket } from '/static/hooks/useWebSocket.js';

// ── Constantes ───────────────────────────────────────────────────────────────
const MAX_CHAT = 300;

// ── Estado inicial ───────────────────────────────────────────────────────────
function makeInitialState() {
  return {
    connected: false,
    historyLoaded: false,
    initialLoad: true,
    ircConnected: false,
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
      lastSync: null, // FollowerSyncEvent mas reciente
      progress: null, // FollowerProgressEvent en curso
      allNewLabels: [], // Labels acumulados de toda la sesion
      allLostLabels: [],
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

    case 'irc_status':
      return { ...state, ircConnected: action.data.connected };

    case 'chat_message': {
      const newMsg = action.data;
      const exists = state.chatMessages.some(
        m =>
          (m.id && newMsg.id && m.id === newMsg.id) ||
          (m.message_id && newMsg.message_id && m.message_id === newMsg.message_id) ||
          (m.timestamp === newMsg.timestamp &&
            m.username === newMsg.username &&
            (m.text || m.message) === (newMsg.text || newMsg.message))
      );
      if (exists) {
        return state;
      }
      const msgs = [...state.chatMessages, newMsg];
      return { ...state, chatMessages: msgs.length > MAX_CHAT ? msgs.slice(-MAX_CHAT) : msgs };
    }

    case 'user_join': {
      const next = new Map(state.ircUsers);
      const nowISO = action.data.timestamp || new Date().toISOString();
      const existing = next.get(action.data.username);
      next.set(action.data.username, {
        ...action.data,
        present: true,
        joinedAt: existing?.joinedAt || nowISO,
        partedAt: null,
      });
      return { ...state, ircUsers: next };
    }

    case 'user_part': {
      const next = new Map(state.ircUsers);
      const nowISO = action.data.timestamp || new Date().toISOString();
      const existing = next.get(action.data.username);
      if (existing) {
        next.set(action.data.username, { ...existing, present: false, partedAt: nowISO });
      } else {
        next.set(action.data.username, { ...action.data, present: false, partedAt: nowISO });
      }
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

    case 'follower_sync': {
      const syncData = action.data;
      const prev = state.followers;

      // Extraer user_id del formato "[123456] NombreUsuario ..."
      const extractId = label => {
        const m = label.match(/^\[(\d+)\]/);
        return m ? m[1] : label;
      };

      if (syncData.is_first_sync) {
        // Primera carga: solo establecer total, no acumular labels
        return {
          ...state,
          followers: {
            ...prev,
            lastSync: syncData,
            progress: null,
            allNewLabels: prev.allNewLabels || [],
            allLostLabels: prev.allLostLabels || [],
          },
        };
      }

      // Acumular labels deduplicando por user_id
      const existingNewIds = new Set((prev.allNewLabels || []).map(extractId));
      const existingLostIds = new Set((prev.allLostLabels || []).map(extractId));

      const freshNew = (syncData.new_labels || []).filter(l => !existingNewIds.has(extractId(l)));
      const freshLost = (syncData.lost_labels || []).filter(
        l => !existingLostIds.has(extractId(l))
      );

      const allNewLabels = [...(prev.allNewLabels || []), ...freshNew];
      const allLostLabels = [...(prev.allLostLabels || []), ...freshLost];

      return {
        ...state,
        followers: {
          ...prev,
          lastSync: syncData,
          progress: null,
          allNewLabels,
          allLostLabels,
        },
      };
    }

    case 'follower_progress':
      return { ...state, followers: { ...state.followers, progress: action.data } };

    case 'clip_created': {
      const clips = state.clips.some(c => c.url === action.data.url)
        ? state.clips
        : [action.data, ...state.clips].slice(0, 20);

      const systemMsg = {
        isSystem: true,
        type: action.type,
        timestamp: action.data.timestamp || new Date().toISOString(),
        data: action.data,
      };
      const exists = state.chatMessages.some(
        m => m.isSystem && m.type === systemMsg.type && m.timestamp === systemMsg.timestamp
      );
      const msgs = exists ? state.chatMessages : [...state.chatMessages, systemMsg];

      return {
        ...state,
        clips,
        chatMessages: msgs.length > MAX_CHAT ? msgs.slice(-MAX_CHAT) : msgs,
      };
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

    case 'agent_clear_history':
      return { ...state, agentConversations: [] };

    case 'BOT_EXITED':
      return { ...state, exited: true };

    case 'user_nickname_updated': {
      const { user_id, nickname } = action.data;
      const ircUsers = new Map(state.ircUsers);

      let targetKey = user_id;
      if (!targetKey && action.data.username) {
        for (const [k, u] of ircUsers.entries()) {
          if (u.username?.toLowerCase() === action.data.username.toLowerCase()) {
            targetKey = k;
            break;
          }
        }
      }

      if (targetKey && ircUsers.has(targetKey)) {
        const u = ircUsers.get(targetKey);
        ircUsers.set(targetKey, {
          ...u,
          nickname,
        });
      }

      const systemMsg = {
        isSystem: true,
        type: action.type,
        timestamp: action.data.timestamp || new Date().toISOString(),
        data: action.data,
      };

      const exists = state.chatMessages.some(
        m => m.isSystem && m.type === systemMsg.type && m.timestamp === systemMsg.timestamp
      );
      const msgs = exists ? state.chatMessages : [...state.chatMessages, systemMsg];

      return {
        ...state,
        ircUsers,
        chatMessages: msgs.length > MAX_CHAT ? msgs.slice(-MAX_CHAT) : msgs,
      };
    }

    case 'user_role_updated': {
      const { user_id, is_bot, is_moderator, is_vip, is_subscriber, sub_tier } = action.data;
      const ircUsers = new Map(state.ircUsers);

      // Buscar por user_id o username
      let targetKey = user_id;
      if (!targetKey && action.data.username) {
        for (const [k, u] of ircUsers.entries()) {
          if (u.username?.toLowerCase() === action.data.username.toLowerCase()) {
            targetKey = k;
            break;
          }
        }
      }

      if (targetKey && ircUsers.has(targetKey)) {
        const u = ircUsers.get(targetKey);
        ircUsers.set(targetKey, {
          ...u,
          is_bot: is_bot ?? u.is_bot,
          is_moderator: is_moderator ?? u.is_moderator,
          is_vip: is_vip ?? u.is_vip,
          is_subscriber: is_subscriber ?? u.is_subscriber,
          sub_tier: sub_tier ?? u.sub_tier,
        });
      }

      const systemMsg = {
        isSystem: true,
        type: action.type,
        timestamp: action.data.timestamp || new Date().toISOString(),
        data: action.data,
      };

      const exists = state.chatMessages.some(
        m => m.isSystem && m.type === systemMsg.type && m.timestamp === systemMsg.timestamp
      );
      const msgs = exists ? state.chatMessages : [...state.chatMessages, systemMsg];

      return {
        ...state,
        ircUsers,
        chatMessages: msgs.length > MAX_CHAT ? msgs.slice(-MAX_CHAT) : msgs,
      };
    }

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
      const exists = state.chatMessages.some(
        m => m.isSystem && m.type === systemMsg.type && m.timestamp === systemMsg.timestamp
      );
      if (exists) {
        return state;
      }
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

// ── ServiceWorker Registration (PWA) ──────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
