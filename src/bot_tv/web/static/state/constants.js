/** @typedef {import('./types.js').AppState} AppState */

export const MAX_CHAT = 300;
export const MAX_PARTED_USERS = 200;
export const MAX_AGENT_CONVERSATIONS = 100;
export const MAX_FOLLOWER_LABELS = 500;
export const MAX_TOASTS = 20;
export const MAX_CLIPS = 20;

let nextMsgUid = 1;

/**
 * Genera un identificador único local para entradas del feed de chat.
 * @returns {string}
 */
export function createMsgUid() {
  return `msg-${nextMsgUid++}`;
}

/**
 * Construye el estado inicial de la aplicación.
 * @returns {AppState}
 */
export function makeInitialState() {
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
    ircUsers: new Map(),
    ircEvents: [],
    followers: {
      lastSync: null,
      progress: null,
      allNewLabels: [],
      allLostLabels: [],
    },
    clips: [],
    agentConversations: [],
    exited: false,
    toasts: [],
  };
}
