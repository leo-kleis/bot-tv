import { h, useEffect, useRef } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';

const html = htm.bind(h);

// Convierte color_rgb [r,g,b] a string CSS
function toRgb(rgb) {
  if (!rgb || rgb.length < 3) return 'var(--text)';
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
}

// Formatea HH:MM desde ISO timestamp
function fmtTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  } catch (_) { return ''; }
}

function roleClass(role) {
  if (!role) return 'visitor';
  if (role === 'Broadcaster') return 'broadcaster';
  if (role === 'Bot') return 'bot';
  if (role === 'Visita') return 'visitor';
  return 'follower'; // fecha de follow
}

function roleDisplay(role) {
  if (!role || role === 'Visita') return null;
  return role;
}

// Mensaje de chat
function ChatMessage({ msg }) {
  const color = toRgb(msg.color_rgb);
  const rClass = roleClass(msg.role);
  const rLabel = roleDisplay(msg.role);

  return html`
    <div class="chat-msg ${msg.is_bot ? 'is-bot' : ''}">
      <span class="chat-time">${fmtTime(msg.timestamp)}</span>
      <span class="chat-author" style="color:${color}">
        ${msg.nickname
          ? html`<span class="chat-nickname">${msg.nickname}</span><span class="chat-display"> ${msg.display_name}</span>`
          : html`<span class="chat-nickname">${msg.display_name}</span>`
        }
      </span>
      ${rLabel ? html`<span class="chat-role">(${rLabel})</span>` : null}
      <span class="chat-text">${msg.text}</span>
    </div>
  `;
}

// Usuario IRC
function IrcUser({ user }) {
  const color = toRgb(user.color_rgb);
  const rClass = roleClass(user.role);
  const name = user.nickname || user.display_name || user.username;

  return html`
    <div class="irc-user">
      <span class="irc-dot" style="background:${color}"></span>
      <span class="irc-name" style="color:${color}">${name}</span>
      ${user.role && user.role !== 'Visita'
        ? html`<span class="irc-role-tag">${user.role}</span>`
        : null
      }
    </div>
  `;
}

export function ChatTab({ chatMessages, ircUsers, showIrcMobile, onToggleIrc }) {
  const feedRef = useRef(null);
  const autoScrollRef = useRef(true);

  // Auto-scroll solo si el usuario no subió manualmente
  useEffect(() => {
    const el = feedRef.current;
    if (!el || !autoScrollRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [chatMessages]);

  function onScroll() {
    const el = feedRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    autoScrollRef.current = atBottom;
  }

  const users = [...ircUsers.values()].sort((a, b) =>
    (a.display_name || a.username).localeCompare(b.display_name || b.username)
  );

  return html`
    <div class="chat-tab ${showIrcMobile ? 'irc-open-mobile' : ''}">

      <!-- Panel Chat (izquierda) -->
      <div class="chat-panel">
        <div class="chat-panel-header">
          <span>Chat</span>
          <span style="color:var(--text-muted);font-size:10px">${chatMessages.length} msgs</span>
        </div>
        <div
          class="chat-feed"
          ref=${feedRef}
          onScroll=${onScroll}
          id="chat-feed"
        >
          ${chatMessages.length === 0 ? html`
            <div class="chat-empty">
              <span class="empty-icon"><i class="fa-regular fa-comments fa-3x" style="color:var(--text-muted);margin-bottom:12px"></i></span>
              <span>Esperando mensajes...</span>
            </div>
          ` : chatMessages.map((m, i) => html`<${ChatMessage} key=${m.timestamp + i} msg=${m} />`)}
        </div>
      </div>

      <!-- Overlay móvil -->
      ${showIrcMobile ? html`<div class="irc-overlay-mobile" onClick=${() => onToggleIrc(false)}></div>` : null}

      <!-- Panel IRC Usuarios (derecha) -->
      <div class="irc-panel">
        <div class="irc-panel-header">
          <span>En canal</span>
          <span class="irc-count">${users.length}</span>
        </div>
        <div class="irc-feed" id="irc-feed">
          ${users.length === 0 ? html`
            <div style="padding:16px 10px;color:var(--text-muted);font-size:11px;text-align:center">Vacío</div>
          ` : users.map(u => html`<${IrcUser} key=${u.username} user=${u} />`)}
        </div>
      </div>

    </div>
  `;
}
