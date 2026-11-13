import { MAX_PARTED_USERS, MAX_TOASTS } from './constants.js';
import { appendSystemMessage, findIrcUserKey, updateChatUserMessages } from './chatUtils.js';

/** @typedef {import('./types.js').AppState} AppState */
/** @typedef {import('./types.js').IrcUser} IrcUser */
/** @typedef {import('./types.js').ToastItem} ToastItem */

/**
 * Compara si el color RGB de dos usuarios es equivalente.
 * @param {number[] | null | undefined} a
 * @param {number[] | null | undefined} b
 * @returns {boolean}
 */
function isSameRgb(a, b) {
  if (a === b) return true;
  if (!a || !b || a.length !== b.length) return false;
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2];
}

/**
 * Verifica si un evento user_join repite exactamente el estado actual del usuario.
 * @param {IrcUser} existing
 * @param {IrcUser} incoming
 * @returns {boolean}
 */
function isSameJoinState(existing, incoming) {
  return (
    existing.present === true &&
    existing.partedAt === null &&
    existing.user_id === incoming.user_id &&
    existing.username === incoming.username &&
    existing.display_name === incoming.display_name &&
    existing.nickname === incoming.nickname &&
    existing.role === incoming.role &&
    existing.is_bot === incoming.is_bot &&
    existing.is_moderator === incoming.is_moderator &&
    existing.is_vip === incoming.is_vip &&
    existing.is_subscriber === incoming.is_subscriber &&
    existing.sub_tier === incoming.sub_tier &&
    existing.timestamp === incoming.timestamp &&
    isSameRgb(existing.color_rgb, incoming.color_rgb)
  );
}

/**
 * Maneja el ingreso de un usuario al canal IRC evitando clonar el Map si no hubo cambios.
 * @param {AppState} state
 * @param {IrcUser} data
 * @returns {AppState}
 */
export function handleUserJoin(state, data) {
  const nowISO = data.timestamp || new Date().toISOString();
  const key = data.user_id || data.username;
  if (!key) return state;

  const existingKey = findIrcUserKey(state.ircUsers, data.user_id, data.username);
  const existing = existingKey ? state.ircUsers.get(existingKey) : undefined;

  if (existing && existingKey === key && isSameJoinState(existing, data)) {
    return state;
  }

  const next = new Map(state.ircUsers);
  if (existingKey && existingKey !== key) {
    next.delete(existingKey);
  }
  next.set(key, {
    ...data,
    present: true,
    joinedAt: existing?.joinedAt || nowISO,
    partedAt: null,
  });
  return { ...state, ircUsers: next };
}

/**
 * Maneja la salida de un usuario del canal IRC y acota el historial de desconectados.
 * @param {AppState} state
 * @param {IrcUser} data
 * @returns {AppState}
 */
export function handleUserPart(state, data) {
  const nowISO = data.timestamp || new Date().toISOString();
  const key = data.user_id || data.username;
  const targetKey = findIrcUserKey(state.ircUsers, data.user_id, data.username);

  if (!targetKey && !key) return state;

  if (targetKey) {
    const existing = state.ircUsers.get(targetKey);
    if (existing && existing.present === false && existing.partedAt === nowISO) {
      return state;
    }
  }

  const next = new Map(state.ircUsers);
  if (targetKey) {
    const existing = next.get(targetKey);
    if (existing) {
      next.set(targetKey, { ...existing, present: false, partedAt: nowISO });
    }
  } else if (key) {
    next.set(key, { ...data, present: false, partedAt: nowISO });
  }

  // Limitar usuarios desconectados (present === false) a MAX_PARTED_USERS
  /** @type {Array<[string, string]>} */
  const partedEntries = [];
  for (const [k, u] of next.entries()) {
    if (u.present === false) {
      partedEntries.push([k, u.partedAt || u.timestamp || '']);
    }
  }
  if (partedEntries.length > MAX_PARTED_USERS) {
    partedEntries.sort((a, b) => a[1].localeCompare(b[1]));
    const toDelete = partedEntries.length - MAX_PARTED_USERS;
    for (let i = 0; i < toDelete; i++) {
      next.delete(partedEntries[i][0]);
    }
  }

  return { ...state, ircUsers: next };
}

/**
 * Actualiza el apodo de un usuario en IRC y en mensajes previos solo si cambió.
 * @param {AppState} state
 * @param {{ user_id?: string, username?: string, nickname?: string | null, timestamp?: string, display_name?: string }} data
 * @returns {AppState}
 */
export function handleUserNicknameUpdated(state, data) {
  const { user_id, username, nickname = null } = data;
  let nextIrcUsers = state.ircUsers;

  const targetKey = findIrcUserKey(state.ircUsers, user_id, username);
  if (targetKey) {
    const current = state.ircUsers.get(targetKey);
    if (current && current.nickname !== nickname) {
      nextIrcUsers = new Map(state.ircUsers);
      nextIrcUsers.set(targetKey, { ...current, nickname });
    }
  }

  const updatedMessages = updateChatUserMessages(state.chatMessages, user_id, username, m =>
    m.nickname === nickname ? m : { ...m, nickname }
  );
  const nextMessages = appendSystemMessage(updatedMessages, 'user_nickname_updated', data);

  if (nextIrcUsers === state.ircUsers && nextMessages === state.chatMessages) {
    return state;
  }

  return {
    ...state,
    ircUsers: nextIrcUsers,
    chatMessages: nextMessages,
  };
}

/**
 * Resuelve el rol textual considerando la bandera de bot.
 * @param {string | undefined} currentRole
 * @param {boolean | undefined} isBot
 * @returns {string | undefined}
 */
function resolveBotRole(currentRole, isBot) {
  if (isBot) return 'Bot';
  if (currentRole === 'Bot') return 'Visita';
  return currentRole;
}

/**
 * Actualiza roles/banderas de un usuario en IRC y mensajes previos solo cuando cambian.
 * @param {AppState} state
 * @param {{
 *   user_id?: string,
 *   username?: string,
 *   display_name?: string,
 *   timestamp?: string,
 *   is_bot?: boolean,
 *   is_moderator?: boolean,
 *   is_vip?: boolean,
 *   is_subscriber?: boolean,
 *   sub_tier?: string | null
 * }} data
 * @returns {AppState}
 */
export function handleUserRoleUpdated(state, data) {
  const { user_id, username, is_bot, is_moderator, is_vip, is_subscriber, sub_tier } = data;
  let nextIrcUsers = state.ircUsers;

  const targetKey = findIrcUserKey(state.ircUsers, user_id, username);
  if (targetKey) {
    const current = state.ircUsers.get(targetKey);
    if (current) {
      const updatedIsBot = is_bot !== undefined ? is_bot : current.is_bot;
      const updatedIsMod = is_moderator !== undefined ? is_moderator : current.is_moderator;
      const updatedIsVip = is_vip !== undefined ? is_vip : current.is_vip;
      const updatedIsSub = is_subscriber !== undefined ? is_subscriber : current.is_subscriber;
      const updatedSubTier = sub_tier !== undefined ? sub_tier : current.sub_tier;
      const updatedRole = resolveBotRole(current.role, updatedIsBot);

      const changed =
        current.is_bot !== updatedIsBot ||
        current.is_moderator !== updatedIsMod ||
        current.is_vip !== updatedIsVip ||
        current.is_subscriber !== updatedIsSub ||
        current.sub_tier !== updatedSubTier ||
        current.role !== updatedRole;

      if (changed) {
        nextIrcUsers = new Map(state.ircUsers);
        nextIrcUsers.set(targetKey, {
          ...current,
          is_bot: updatedIsBot,
          is_moderator: updatedIsMod,
          is_vip: updatedIsVip,
          is_subscriber: updatedIsSub,
          sub_tier: updatedSubTier,
          role: updatedRole,
        });
      }
    }
  }

  const updatedMessages = updateChatUserMessages(state.chatMessages, user_id, username, m => {
    const updatedIsBot = is_bot !== undefined ? is_bot : m.is_bot;
    const updatedRole = resolveBotRole(m.role, updatedIsBot);
    if (m.is_bot === updatedIsBot && m.role === updatedRole) {
      return m;
    }
    return { ...m, is_bot: updatedIsBot, role: updatedRole };
  });

  const nextMessages = appendSystemMessage(updatedMessages, 'user_role_updated', data);

  if (nextIrcUsers === state.ircUsers && nextMessages === state.chatMessages) {
    return state;
  }

  return {
    ...state,
    ircUsers: nextIrcUsers,
    chatMessages: nextMessages,
  };
}

/**
 * Resuelve el rol tras un evento de follow respetando Broadcaster y Bot.
 * @param {string | undefined} currentRole
 * @param {boolean | undefined} isBot
 * @param {string | undefined} incomingRole
 * @returns {string | undefined}
 */
function resolveFollowRole(currentRole, isBot, incomingRole) {
  if (currentRole === 'Broadcaster' || isBot || currentRole === 'Bot') {
    return currentRole;
  }
  return incomingRole || currentRole;
}

/**
 * Maneja un evento twitch_follow actualizando usuario IRC, mensajes previos y toasts.
 * @param {AppState} state
 * @param {{ user_id?: string, username?: string, display_name?: string, role?: string, timestamp?: string }} data
 * @returns {AppState}
 */
export function handleTwitchFollow(state, data) {
  const { user_id, username, display_name, role } = data;
  let nextIrcUsers = state.ircUsers;

  const targetKey = findIrcUserKey(state.ircUsers, user_id, username);
  if (targetKey) {
    const current = state.ircUsers.get(targetKey);
    if (current) {
      const updatedRole = resolveFollowRole(current.role, current.is_bot, role);
      if (updatedRole !== current.role) {
        nextIrcUsers = new Map(state.ircUsers);
        nextIrcUsers.set(targetKey, { ...current, role: updatedRole });
      }
    }
  }

  const updatedMessages = updateChatUserMessages(state.chatMessages, user_id, username, m => {
    const updatedRole = resolveFollowRole(m.role, m.is_bot, role);
    if (updatedRole === m.role) return m;
    return { ...m, role: updatedRole };
  });

  const nextMessages = appendSystemMessage(updatedMessages, 'twitch_follow', data);

  /** @type {ToastItem} */
  const followToast = {
    id: `tf-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    type: 'twitch_follow',
    title: '¡Nuevo Seguidor!',
    data: { message: `${display_name || username || 'Alguien'} comenzó a seguir el canal.` },
  };

  return {
    ...state,
    toasts: [...state.toasts, followToast].slice(-MAX_TOASTS),
    ircUsers: nextIrcUsers,
    chatMessages: nextMessages,
  };
}
