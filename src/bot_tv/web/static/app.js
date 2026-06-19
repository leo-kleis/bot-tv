import { h, render, useState, useEffect, useReducer, useRef } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';
import { App } from '/static/components/App.js';

const html = htm.bind(h);

// Cargar y aplicar tamaño de fuente guardado antes de renderizar
const savedFontSize = localStorage.getItem('font-size') || '14.5px';
document.documentElement.style.setProperty('--font-size', savedFontSize);

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
      startedAt: null,
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
      return { ...state, connected: true, exited: false };

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
  const timeoutIdRef = useRef(null);
  const connectFnRef = useRef(null);

  useEffect(() => {
    let destroyed = false;

    function connect() {
      if (destroyed) return;

      if (timeoutIdRef.current) {
        clearTimeout(timeoutIdRef.current);
        timeoutIdRef.current = null;
      }

      if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
        return;
      }

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
        
        if (timeoutIdRef.current) clearTimeout(timeoutIdRef.current);

        timeoutIdRef.current = setTimeout(() => {
          reconnectRef.current = Math.min(reconnectRef.current * 1.5, 30000);
          connect();
        }, reconnectRef.current);
      };

      ws.onerror = () => ws.close();
    }

    connectFnRef.current = connect;
    connect();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
          reconnectRef.current = 1000;
          connect();
        }
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      destroyed = true;
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (timeoutIdRef.current) clearTimeout(timeoutIdRef.current);
      wsRef.current?.close();
    };
  }, []);

  const triggerReconnect = () => {
    reconnectRef.current = 1000;
    if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
      connectFnRef.current?.();
    } else {
      wsRef.current.close();
    }
  };

  return html`<${App} state=${state} dispatch=${dispatch} onReconnect=${triggerReconnect} />`;
}

// ── Mount ─────────────────────────────────────────────────────────────────────
render(html`<${Root} />`, document.getElementById('app'));
