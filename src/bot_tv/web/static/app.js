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
      const key = action.data.user_id || action.data.username;
      let existingKey = next.has(key) ? key : null;
      if (!existingKey) {
        for (const [k, u] of next.entries()) {
          if (
            (action.data.user_id && u.user_id === action.data.user_id) ||
            (action.data.username &&
              u.username?.toLowerCase() === action.data.username.toLowerCase())
          ) {
            existingKey = k;
            break;
          }
        }
      }
      const existing = existingKey ? next.get(existingKey) : null;
      if (existingKey && existingKey !== key) {
        next.delete(existingKey);
      }
      next.set(key, {
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
      const key = action.data.user_id || action.data.username;
      let targetKey = next.has(key) ? key : null;
      if (!targetKey) {
        for (const [k, u] of next.entries()) {
          if (
            (action.data.user_id && u.user_id === action.data.user_id) ||
            (action.data.username &&
              u.username?.toLowerCase() === action.data.username.toLowerCase())
          ) {
            targetKey = k;
            break;
          }
        }
      }
      if (targetKey) {
        const existing = next.get(targetKey);
        next.set(targetKey, { ...existing, present: false, partedAt: nowISO });
      } else {
        next.set(key, { ...action.data, present: false, partedAt: nowISO });
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
          broadcasterName: action.data.broadcaster_name || state.stream.broadcasterName,
          viewerCount: null,
          viewerDiff: null,
          startedAt: null,
        },
      };

    case 'stream_update':
      return {
        ...state,
        stream: {
          ...state.stream,
          broadcasterName: action.data.broadcaster_name || state.stream.broadcasterName,
          title: action.data.title !== undefined ? action.data.title : state.stream.title,
          category:
            action.data.category !== undefined ? action.data.category : state.stream.category,
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

      const followerToasts = [];
      const getCleanName = label => label.replace(/^\[\d+\]\s*/, '').split(' (')[0] || label;

      // Generar Toast agrupado para Nuevos Seguidores
      if (freshNew.length === 1) {
        const name = getCleanName(freshNew[0]);
        followerToasts.push({
          id: `fn-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          type: 'follower_new',
          title: '¡Nuevo Seguidor!',
          data: { message: `${name} comenzó a seguirte.` },
        });
      } else if (freshNew.length === 2) {
        const name1 = getCleanName(freshNew[0]);
        const name2 = getCleanName(freshNew[1]);
        followerToasts.push({
          id: `fn-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          type: 'follower_new',
          title: '¡Nuevos Seguidores!',
          data: { message: `${name1} y ${name2} comenzaron a seguirte.` },
        });
      } else if (freshNew.length >= 3) {
        const name1 = getCleanName(freshNew[0]);
        const name2 = getCleanName(freshNew[1]);
        followerToasts.push({
          id: `fn-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          type: 'follower_new',
          title: `¡${freshNew.length} Nuevos Seguidores!`,
          data: {
            message: `${name1}, ${name2} y ${freshNew.length - 2} más comenzaron a seguirte.`,
          },
        });
      }

      // Generar Toast agrupado para Seguidores Perdidos
      if (freshLost.length === 1) {
        const name = getCleanName(freshLost[0]);
        followerToasts.push({
          id: `fl-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          type: 'follower_lost',
          title: 'Seguidor Perdido',
          data: { message: `${name} dejó de seguirte.` },
        });
      } else if (freshLost.length === 2) {
        const name1 = getCleanName(freshLost[0]);
        const name2 = getCleanName(freshLost[1]);
        followerToasts.push({
          id: `fl-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          type: 'follower_lost',
          title: 'Seguidores Perdidos',
          data: { message: `${name1} y ${name2} dejaron de seguirte.` },
        });
      } else if (freshLost.length >= 3) {
        const name1 = getCleanName(freshLost[0]);
        const name2 = getCleanName(freshLost[1]);
        followerToasts.push({
          id: `fl-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          type: 'follower_lost',
          title: `${freshLost.length} Seguidores Perdidos`,
          data: {
            message: `${name1}, ${name2} y ${freshLost.length - 2} más dejaron de seguirte.`,
          },
        });
      }

      const addedUnread = freshNew.length + freshLost.length;

      return {
        ...state,
        toasts: followerToasts.length > 0 ? [...state.toasts, ...followerToasts] : state.toasts,
        followers: {
          ...prev,
          lastSync: syncData,
          progress: null,
          unreadCount: (prev.unreadCount || 0) + addedUnread,
          allNewLabels,
          allLostLabels,
        },
      };
    }

    case 'CLEAR_UNREAD_FOLLOWERS':
      return { ...state, followers: { ...state.followers, unreadCount: 0 } };

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
      const { user_id, username, nickname } = action.data;
      const ircUsers = new Map(state.ircUsers);

      let targetKey = null;
      if (user_id && ircUsers.has(user_id)) {
        targetKey = user_id;
      } else if (username && ircUsers.has(username)) {
        targetKey = username;
      } else {
        for (const [k, u] of ircUsers.entries()) {
          if (
            (user_id && u.user_id === user_id) ||
            (username && u.username?.toLowerCase() === username.toLowerCase())
          ) {
            targetKey = k;
            break;
          }
        }
      }

      if (targetKey) {
        const u = ircUsers.get(targetKey);
        ircUsers.set(targetKey, {
          ...u,
          nickname,
        });
      }

      const updatedChatMessages = state.chatMessages.map(m => {
        if (m.isSystem) return m;
        const matchesUser =
          (user_id && m.user_id === user_id) ||
          (username && m.username?.toLowerCase() === username.toLowerCase());
        if (matchesUser) {
          return { ...m, nickname };
        }
        return m;
      });

      const systemMsg = {
        isSystem: true,
        type: action.type,
        timestamp: action.data.timestamp || new Date().toISOString(),
        data: action.data,
      };

      const exists = updatedChatMessages.some(
        m => m.isSystem && m.type === systemMsg.type && m.timestamp === systemMsg.timestamp
      );
      const msgs = exists ? updatedChatMessages : [...updatedChatMessages, systemMsg];

      return {
        ...state,
        ircUsers,
        chatMessages: msgs.length > MAX_CHAT ? msgs.slice(-MAX_CHAT) : msgs,
      };
    }

    case 'user_role_updated': {
      const { user_id, username, is_bot, is_moderator, is_vip, is_subscriber, sub_tier } =
        action.data;
      const ircUsers = new Map(state.ircUsers);

      let targetKey = null;
      if (user_id && ircUsers.has(user_id)) {
        targetKey = user_id;
      } else if (username && ircUsers.has(username)) {
        targetKey = username;
      } else {
        for (const [k, u] of ircUsers.entries()) {
          if (
            (user_id && u.user_id === user_id) ||
            (username && u.username?.toLowerCase() === username.toLowerCase())
          ) {
            targetKey = k;
            break;
          }
        }
      }

      if (targetKey) {
        const u = ircUsers.get(targetKey);
        const updatedIsBot = is_bot !== undefined ? is_bot : u.is_bot;
        let role = u.role;
        if (updatedIsBot) {
          role = 'Bot';
        } else if (role === 'Bot') {
          role = 'Visita';
        }
        ircUsers.set(targetKey, {
          ...u,
          is_bot: updatedIsBot,
          is_moderator: is_moderator !== undefined ? is_moderator : u.is_moderator,
          is_vip: is_vip !== undefined ? is_vip : u.is_vip,
          is_subscriber: is_subscriber !== undefined ? is_subscriber : u.is_subscriber,
          sub_tier: sub_tier !== undefined ? sub_tier : u.sub_tier,
          role,
        });
      }

      const updatedChatMessages = state.chatMessages.map(m => {
        if (m.isSystem) return m;
        const matchesUser =
          (user_id && m.user_id === user_id) ||
          (username && m.username?.toLowerCase() === username.toLowerCase());
        if (matchesUser) {
          const updatedIsBot = is_bot !== undefined ? is_bot : m.is_bot;
          let role = m.role;
          if (updatedIsBot) {
            role = 'Bot';
          } else if (role === 'Bot') {
            role = 'Visita';
          }
          return {
            ...m,
            is_bot: updatedIsBot,
            role,
          };
        }
        return m;
      });

      const systemMsg = {
        isSystem: true,
        type: action.type,
        timestamp: action.data.timestamp || new Date().toISOString(),
        data: action.data,
      };

      const exists = updatedChatMessages.some(
        m => m.isSystem && m.type === systemMsg.type && m.timestamp === systemMsg.timestamp
      );
      const msgs = exists ? updatedChatMessages : [...updatedChatMessages, systemMsg];

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
  useWebSocket(dispatch);

  return html`<${App} state=${state} dispatch=${dispatch} />`;
}

// ── Mount ─────────────────────────────────────────────────────────────────────
render(html`<${Root} />`, document.getElementById('app'));

// ── ServiceWorker Registration (PWA) ──────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
