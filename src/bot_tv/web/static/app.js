import { h, render, useState, useEffect, useReducer, useRef } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';
import { App } from '/static/components/App.js';

const html = htm.bind(h);

// ── Registro del service worker ──────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

// ── Constantes ───────────────────────────────────────────────────────────────
const MAX_CHAT = 300;
const MAX_IRC_HISTORY = 100;

// ── Estado inicial ───────────────────────────────────────────────────────────
function makeInitialState() {
  return {
    connected: false,
    historyLoaded: false,
    stream: {
      online: false,
      broadcasterName: '',
      title: '',
      category: '',
      viewerCount: null,
      viewerDiff: null,
    },
    chatMessages: [],
    ircUsers: new Map(),           // username → {display_name, nickname, color_rgb, role}
    ircEvents: [],                  // log de JOIN/PART para mostrar en historial si hace falta
    followers: {
      lastSync: null,              // FollowerSyncEvent más reciente
      progress: null,              // FollowerProgressEvent en curso
    },
    clips: [],
    agentConversations: [],
    exited: false,
  };
}

// ── Reducer ───────────────────────────────────────────────────────────────────
function reducer(state, action) {
  switch (action.type) {
    case 'WS_CONNECTED':
      return { ...state, connected: true };

    case 'WS_DISCONNECTED':
      return { ...state, connected: false, historyLoaded: false };

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
      const pendingIdx = list.findLastIndex(c => c.question === action.data.question && c.response === null);
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

    default:
      return state;
  }
}

// ── Root Component ────────────────────────────────────────────────────────────
function Root() {
  const [state, dispatch] = useReducer(reducer, null, makeInitialState);
  const wsRef = useRef(null);
  const reconnectRef = useRef(1000);

  useEffect(() => {
    let destroyed = false;

    function connect() {
      if (destroyed) return;
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${proto}//${location.host}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectRef.current = 1000;
        dispatch({ type: 'WS_CONNECTED' });
      };

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'history_end') {
            dispatch({ type: 'HISTORY_END' });
          } else {
            dispatch({ type: msg.type, data: msg.data });
          }
        } catch (_) {}
      };

      ws.onclose = () => {
        if (destroyed) return;
        dispatch({ type: 'WS_DISCONNECTED' });
        setTimeout(() => {
          reconnectRef.current = Math.min(reconnectRef.current * 1.5, 30000);
          connect();
        }, reconnectRef.current);
      };

      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      destroyed = true;
      wsRef.current?.close();
    };
  }, []);

  return html`<${App} state=${state} dispatch=${dispatch} />`;
}

// ── Mount ─────────────────────────────────────────────────────────────────────
render(html`<${Root} />`, document.getElementById('app'));
