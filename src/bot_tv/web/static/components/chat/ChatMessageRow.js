import { html, memo } from 'preact-setup';
import { getEventDetails } from '../event-config.js';
import { toRgb, fmtTime } from 'lib/utils';
import { UserAvatar } from '../UserAvatar.js';
import { parseEmotes } from '/static/lib/emotes.js';

/** @typedef {import('/static/lib/emotes.js').EmotesMap} EmotesMap */
/** @typedef {import('/static/state/types.js').ChatMessage} ChatMessage */
/** @typedef {import('/static/state/types.js').SystemChatMessage} SystemChatMessage */

/**
 * Normaliza la etiqueta de rol visible en el mensaje.
 * @param {string | undefined} role
 * @returns {string}
 */
function roleDisplay(role) {
  if (!role || role === 'Visita') return 'Visita';
  return role;
}

/**
 * Encabezado de grupo de mensajes: avatar accesible + nombre + rol + hora + texto.
 */
export const ChatMessageGroup = memo(function ChatMessageGroup({
  msg,
  emotesMap,
  onUserClick,
  onMsgContext,
}) {
  const color = toRgb(msg.color_rgb);
  const rLabel = roleDisplay(msg.role);
  const userLabel = msg.display_name || msg.username || 'usuario';

  /** @param {MouseEvent} e */
  const handleContext = e => onMsgContext(e, msg);
  const handleUserAction = () => onUserClick(msg);

  /** @param {KeyboardEvent} e */
  const handleAuthorKeyDown = e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onUserClick(msg);
    }
  };

  return html`
    <div class="chat-msg-group ${msg.is_bot ? 'is-bot' : ''}" onContextMenu=${handleContext}>
      <button
        type="button"
        class="chat-avatar-btn"
        aria-label=${`Ver perfil de ${userLabel}`}
        onClick=${handleUserAction}
        style="background:none;border:none;padding:0;margin:0;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;border-radius:50%;flex-shrink:0;"
      >
        <${UserAvatar}
          userId=${msg.user_id}
          displayName=${msg.display_name || msg.username || '?'}
          color=${color}
          size="md"
        />
      </button>
      <div class="chat-msg-content">
        <div class="chat-msg-header">
          <span
            class="chat-author"
            role="button"
            tabIndex=${0}
            aria-label=${`Ver perfil de ${userLabel}`}
            style="color:${color}; cursor:pointer;"
            onClick=${handleUserAction}
            onKeyDown=${handleAuthorKeyDown}
          >
            ${
              msg.nickname
                ? html`<span class="chat-nickname">${msg.nickname}</span
                    ><span class="chat-display"> ${msg.display_name}</span>`
                : html`<span class="chat-nickname">${msg.display_name}</span>`
            }
          </span>
          ${rLabel ? html`<span class="chat-role">(${rLabel})</span>` : null}
          <span class="chat-time">${fmtTime(msg.timestamp)}</span>
        </div>
        <div class="chat-msg-body">${parseEmotes(msg.text, emotesMap, msg.emotes)}</div>
      </div>
    </div>
  `;
});

/**
 * Mensaje continuación del mismo usuario: solo texto y hora visible en hover.
 */
export const ChatMessageCont = memo(function ChatMessageCont({ msg, emotesMap, onMsgContext }) {
  return html`
    <div
      class="chat-msg-cont ${msg.is_bot ? 'is-bot' : ''}"
      onContextMenu=${/** @param {MouseEvent} e */ e => onMsgContext(e, msg)}
    >
      <span class="chat-time-hover">${fmtTime(msg.timestamp)}</span>
      <div class="chat-msg-body">${parseEmotes(msg.text, emotesMap, msg.emotes)}</div>
    </div>
  `;
});

/**
 * Mensaje de alerta o evento del sistema dentro del feed de chat.
 */
export const ChatMessageSystem = memo(function ChatMessageSystem({ msg }) {
  const details = getEventDetails(msg.type);
  const textHtml = details.chatHtml(msg.data, html);
  return html`
    <div class="chat-msg is-system ${details.sysClassName}">
      <span class="chat-time">${fmtTime(msg.timestamp)}</span>
      <span class="sys-icon" aria-hidden="true"><i class="fa-solid ${details.icon}"></i></span>
      <span class="sys-text">${textHtml}</span>
    </div>
  `;
});
