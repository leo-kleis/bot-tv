import {
  MAX_AGENT_CONVERSATIONS,
  MAX_CHAT,
  MAX_CLIPS,
  MAX_FOLLOWER_LABELS,
  MAX_TOASTS,
  createMsgUid,
} from './constants.js';
import { appendSystemMessage } from './chatUtils.js';

/** @typedef {import('./types.js').AgentConversation} AgentConversation */
/** @typedef {import('./types.js').AppState} AppState */
/** @typedef {import('./types.js').ChatMessage} ChatMessage */
/** @typedef {import('./types.js').ClipData} ClipData */
/** @typedef {import('./types.js').FollowerSyncData} FollowerSyncData */
/** @typedef {import('./types.js').ToastItem} ToastItem */

/**
 * Extrae el ID numérico del formato "[123456] NombreUsuario ...".
 * @param {string} label
 * @returns {string}
 */
function extractFollowerId(label) {
  const m = label.match(/^\[(\d+)\]/);
  return m ? m[1] : label;
}

/**
 * Extrae el nombre visible desde una etiqueta de seguidor.
 * @param {string} label
 * @returns {string}
 */
function extractFollowerName(label) {
  return label.replace(/^\[\d+\]\s*/, '').split(' (')[0] || label;
}

/**
 * Construye un toast agrupado para seguidores nuevos o perdidos.
 * @param {string[]} labels
 * @param {boolean} isNew
 * @returns {ToastItem | null}
 */
function buildFollowerToast(labels, isNew) {
  if (labels.length === 0) return null;

  const prefix = isNew ? 'fn' : 'fl';
  const type = isNew ? 'follower_new' : 'follower_lost';
  const actionVerb = isNew ? 'comenzó a seguirte.' : 'dejó de seguirte.';
  const actionVerbPlural = isNew ? 'comenzaron a seguirte.' : 'dejaron de seguirte.';

  let title = '';
  let message = '';

  if (labels.length === 1) {
    title = isNew ? '¡Nuevo Seguidor!' : 'Seguidor Perdido';
    message = `${extractFollowerName(labels[0])} ${actionVerb}`;
  } else if (labels.length === 2) {
    title = isNew ? '¡Nuevos Seguidores!' : 'Seguidores Perdidos';
    message = `${extractFollowerName(labels[0])} y ${extractFollowerName(labels[1])} ${actionVerbPlural}`;
  } else {
    title = isNew ? `¡${labels.length} Nuevos Seguidores!` : `${labels.length} Seguidores Perdidos`;
    message = `${extractFollowerName(labels[0])}, ${extractFollowerName(labels[1])} y ${labels.length - 2} más ${actionVerbPlural}`;
  }

  return {
    id: `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    type,
    title,
    data: { message },
  };
}

/**
 * Agrega un mensaje de chat al historial evitando duplicados.
 * @param {AppState} state
 * @param {ChatMessage} newMsg
 * @returns {AppState}
 */
export function handleChatMessage(state, newMsg) {
  const exists = state.chatMessages.some(
    m =>
      !m.isSystem &&
      ((m.id && newMsg.id && m.id === newMsg.id) ||
        (m.message_id && newMsg.message_id && m.message_id === newMsg.message_id) ||
        (m.timestamp === newMsg.timestamp &&
          m.username === newMsg.username &&
          (m.text || m.message) === (newMsg.text || newMsg.message)))
  );
  if (exists) {
    return state;
  }

  /** @type {ChatMessage} */
  const msgWithUid = {
    ...newMsg,
    _uid: newMsg._uid || newMsg.message_id || newMsg.id || createMsgUid(),
  };
  const msgs = [...state.chatMessages, msgWithUid];
  return { ...state, chatMessages: msgs.length > MAX_CHAT ? msgs.slice(-MAX_CHAT) : msgs };
}

/**
 * @param {AppState} state
 * @param {{ broadcaster_name: string, title: string, category: string, started_at: string }} data
 * @returns {AppState}
 */
export function handleStreamOnline(state, data) {
  return {
    ...state,
    stream: {
      ...state.stream,
      online: true,
      broadcasterName: data.broadcaster_name,
      title: data.title,
      category: data.category,
      startedAt: data.started_at,
    },
  };
}

/**
 * @param {AppState} state
 * @param {{ broadcaster_name?: string, title?: string, category?: string }} data
 * @returns {AppState}
 */
export function handleStreamOffline(state, data) {
  return {
    ...state,
    stream: {
      ...state.stream,
      online: false,
      broadcasterName: data.broadcaster_name || state.stream.broadcasterName,
      title: data.title !== undefined && data.title !== '' ? data.title : state.stream.title,
      category:
        data.category !== undefined && data.category !== '' ? data.category : state.stream.category,
      viewerCount: null,
      viewerDiff: null,
      startedAt: null,
    },
  };
}

/**
 * @param {AppState} state
 * @param {{ broadcaster_name?: string, title?: string, category?: string }} data
 * @returns {AppState}
 */
export function handleStreamUpdate(state, data) {
  return {
    ...state,
    stream: {
      ...state.stream,
      broadcasterName: data.broadcaster_name || state.stream.broadcasterName,
      title: data.title !== undefined ? data.title : state.stream.title,
      category: data.category !== undefined ? data.category : state.stream.category,
    },
  };
}

/**
 * @param {AppState} state
 * @param {{ count: number | null, diff: number | null }} data
 * @returns {AppState}
 */
export function handleViewerUpdate(state, data) {
  if (state.stream.viewerCount === data.count && state.stream.viewerDiff === data.diff) {
    return state;
  }
  return {
    ...state,
    stream: {
      ...state.stream,
      viewerCount: data.count,
      viewerDiff: data.diff,
    },
  };
}

/**
 * @param {AppState} state
 * @param {FollowerSyncData} syncData
 * @returns {AppState}
 */
export function handleFollowerSync(state, syncData) {
  const prev = state.followers;

  if (syncData.is_first_sync) {
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

  const existingNewIds = new Set((prev.allNewLabels || []).map(extractFollowerId));
  const existingLostIds = new Set((prev.allLostLabels || []).map(extractFollowerId));

  const freshNew = (syncData.new_labels || []).filter(
    l => !existingNewIds.has(extractFollowerId(l))
  );
  const freshLost = (syncData.lost_labels || []).filter(
    l => !existingLostIds.has(extractFollowerId(l))
  );

  const allNewLabels = [...(prev.allNewLabels || []), ...freshNew].slice(-MAX_FOLLOWER_LABELS);
  const allLostLabels = [...(prev.allLostLabels || []), ...freshLost].slice(-MAX_FOLLOWER_LABELS);

  /** @type {ToastItem[]} */
  const followerToasts = [];
  const newToast = buildFollowerToast(freshNew, true);
  if (newToast) followerToasts.push(newToast);
  const lostToast = buildFollowerToast(freshLost, false);
  if (lostToast) followerToasts.push(lostToast);

  const addedUnread = freshNew.length + freshLost.length;

  return {
    ...state,
    toasts:
      followerToasts.length > 0
        ? [...state.toasts, ...followerToasts].slice(-MAX_TOASTS)
        : state.toasts,
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

/**
 * @param {AppState} state
 * @param {ClipData} data
 * @returns {AppState}
 */
export function handleClipCreated(state, data) {
  const clips = state.clips.some(c => c.url === data.url)
    ? state.clips
    : [data, ...state.clips].slice(0, MAX_CLIPS);
  const chatMessages = appendSystemMessage(state.chatMessages, 'clip_created', data);

  return {
    ...state,
    clips,
    chatMessages,
  };
}

/**
 * @param {AppState} state
 * @param {{ timestamp: string, question: string }} data
 * @returns {AppState}
 */
export function handleAgentQuestionPending(state, data) {
  /** @type {AgentConversation} */
  const pending = {
    timestamp: data.timestamp,
    question: data.question,
    response: null,
    model: null,
  };
  return {
    ...state,
    agentConversations: [...state.agentConversations, pending].slice(-MAX_AGENT_CONVERSATIONS),
  };
}

/**
 * @param {AppState} state
 * @param {AgentConversation} data
 * @returns {AppState}
 */
export function handleAgentResponse(state, data) {
  const list = [...state.agentConversations];
  const pendingIdx = list.findLastIndex(c => c.question === data.question && c.response === null);
  if (pendingIdx !== -1) {
    list[pendingIdx] = data;
  } else if (!list.some(c => c.timestamp === data.timestamp)) {
    list.push(data);
  }
  return {
    ...state,
    agentConversations:
      list.length > MAX_AGENT_CONVERSATIONS ? list.slice(-MAX_AGENT_CONVERSATIONS) : list,
  };
}
