import { MAX_CHAT, createMsgUid } from './constants.js';

/** @typedef {import('./types.js').ChatEntry} ChatEntry */
/** @typedef {import('./types.js').ChatMessage} ChatMessage */
/** @typedef {import('./types.js').IrcUsersMap} IrcUsersMap */
/** @typedef {import('./types.js').SystemChatMessage} SystemChatMessage */
/** @typedef {import('./types.js').SystemEventPayload} SystemEventPayload */

/**
 * Busca la clave existente de un usuario en el mapa IRC sin clonar el mapa.
 * @param {IrcUsersMap} ircUsers
 * @param {string | undefined} userId
 * @param {string | undefined} username
 * @returns {string | null}
 */
export function findIrcUserKey(ircUsers, userId, username) {
  if (userId && ircUsers.has(userId)) {
    return userId;
  }
  if (username && ircUsers.has(username)) {
    return username;
  }

  const lowerUsername = username ? username.toLowerCase() : null;
  for (const [k, u] of ircUsers.entries()) {
    if (
      (userId && u.user_id === userId) ||
      (lowerUsername && u.username?.toLowerCase() === lowerUsername)
    ) {
      return k;
    }
  }
  return null;
}

/**
 * Verifica si un mensaje de sistema equivalente ya está en el feed.
 * @param {ChatEntry[]} chatMessages
 * @param {string} type
 * @param {string} timestamp
 * @returns {boolean}
 */
export function hasSystemMessage(chatMessages, type, timestamp) {
  return chatMessages.some(m => m.isSystem && m.type === type && m.timestamp === timestamp);
}

/**
 * Agrega un mensaje de sistema al historial deduplicando por tipo y timestamp.
 * @param {ChatEntry[]} chatMessages
 * @param {string} type
 * @param {SystemEventPayload} data
 * @returns {ChatEntry[]}
 */
export function appendSystemMessage(chatMessages, type, data) {
  const timestamp = data.timestamp || new Date().toISOString();
  if (hasSystemMessage(chatMessages, type, timestamp)) {
    return chatMessages;
  }

  /** @type {SystemChatMessage} */
  const systemMsg = {
    _uid: createMsgUid(),
    isSystem: true,
    type,
    timestamp,
    data,
  };
  const next = [...chatMessages, systemMsg];
  return next.length > MAX_CHAT ? next.slice(-MAX_CHAT) : next;
}

/**
 * Actualiza solo los mensajes de un usuario cuyo resultado cambie, evitando
 * clonar el array completo si ningún mensaje fue modificado.
 * @param {ChatEntry[]} chatMessages
 * @param {string | undefined} userId
 * @param {string | undefined} username
 * @param {(msg: ChatMessage) => ChatMessage} mapFn
 * @returns {ChatEntry[]}
 */
export function updateChatUserMessages(chatMessages, userId, username, mapFn) {
  const lowerUsername = username ? username.toLowerCase() : null;
  /** @type {ChatEntry[] | null} */
  let nextMessages = null;

  for (let i = 0; i < chatMessages.length; i++) {
    const entry = chatMessages[i];
    if (entry.isSystem) continue;

    const msg = /** @type {ChatMessage} */ (entry);
    const matchesUser =
      (userId && msg.user_id === userId) ||
      (lowerUsername && msg.username?.toLowerCase() === lowerUsername);
    if (!matchesUser) continue;

    const updated = mapFn(msg);
    if (updated !== msg) {
      if (nextMessages === null) {
        nextMessages = chatMessages.slice();
      }
      nextMessages[i] = updated;
    }
  }

  return nextMessages || chatMessages;
}
