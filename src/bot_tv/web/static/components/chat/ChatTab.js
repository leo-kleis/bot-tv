import { h, useEffect, useRef, useState } from '/static/vendor/preact.module.js';
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
  if (!role || role === 'Visita') return 'Visita';
  return role;
}

function getSystemMessageDetails(msg) {
  const type = msg.type;
  const data = msg.data;

  switch (type) {
    case 'twitch_raid':
      return {
        icon: 'fa-people-group',
        text: html`<strong>${data.from_display_name}</strong> nos hizo raid con <strong>${data.viewer_count}</strong> espectadores!`,
        className: 'sys-raid',
      };
    case 'twitch_subscribe':
      const regalo = data.is_gift ? ' (Regalo)' : '';
      return {
        icon: 'fa-star',
        text: html`<strong>${data.display_name}</strong> se suscribió en Tier <strong>${data.tier}</strong>${regalo}!`,
        className: 'sys-sub',
      };
    case 'twitch_sub_gift':
      const donante = data.is_anonymous ? 'Anónimo' : data.display_name;
      const acum = data.cumulative_total ? ` (Total: ${data.cumulative_total})` : '';
      return {
        icon: 'fa-gift',
        text: html`<strong>${donante}</strong> regaló <strong>${data.total}</strong> subs de Tier <strong>${data.tier}</strong>${acum}!`,
        className: 'sys-sub-gift',
      };
    case 'twitch_sub_message':
      const msgStr = data.message ? ` - "${data.message}"` : '';
      const rachaStr = data.streak_months ? ` (Racha: ${data.streak_months} meses)` : '';
      return {
        icon: 'fa-comments',
        text: html`<strong>${data.display_name}</strong> se resuscribió por <strong>${data.cumulative_months}</strong> meses${rachaStr}!${msgStr}`,
        className: 'sys-sub-resub',
      };
    case 'twitch_cheer':
      const cheerDonante = data.is_anonymous ? 'Anónimo' : data.display_name;
      const cheerMsg = data.message ? ` - "${data.message}"` : '';
      return {
        icon: 'fa-gem',
        text: html`<strong>${cheerDonante}</strong> envió <strong>${data.bits}</strong> bits!${cheerMsg}`,
        className: 'sys-cheer',
      };
    case 'twitch_points_redeem':
      const inputStr = data.user_input ? ` ("${data.user_input}")` : '';
      return {
        icon: 'fa-ticket',
        text: html`<strong>${data.display_name}</strong> canjeó <strong>${data.reward_title}</strong> por <strong>${data.reward_cost}</strong> puntos!${inputStr}`,
        className: 'sys-points',
      };
    case 'prediction_begin':
      return {
        icon: 'fa-circle-question',
        text: html`Predicción iniciada: "<strong>${data.title}</strong>" - Opciones: ${data.outcomes.join(', ')}`,
        className: 'sys-prediction',
      };
    case 'prediction_lock':
      return {
        icon: 'fa-lock',
        text: html`Apuestas cerradas para: "<strong>${data.title}</strong>"`,
        className: 'sys-prediction',
      };
    case 'prediction_end':
      const resultado = data.winning_outcome_title 
        ? html`Ganador: <strong>${data.winning_outcome_title}</strong>` 
        : `Estado: ${data.status}`;
      return {
        icon: 'fa-flag-checkered',
        text: html`Predicción finalizada: "<strong>${data.title}</strong>" - ${resultado}`,
        className: 'sys-prediction',
      };
    case 'twitch_ban':
      const tipo = data.permanent ? 'Baneo permanente' : `Timeout de ${data.duration_seconds}s`;
      const razon = data.reason ? ` (Razón: "${data.reason}")` : '';
      return {
        icon: 'fa-ban',
        text: html`<strong>${data.display_name}</strong> sancionado (${tipo}) por <strong>${data.moderator_name}</strong>${razon}.`,
        className: 'sys-mod',
      };
    case 'twitch_unban':
      return {
        icon: 'fa-key',
        text: html`<strong>${data.display_name}</strong> desbaneado por <strong>${data.moderator_name}</strong>.`,
        className: 'sys-mod-green',
      };
    case 'twitch_chat_clear':
      return {
        icon: 'fa-trash-can',
        text: 'El chat fue limpiado por un moderador.',
        className: 'sys-mod',
      };
    case 'twitch_chat_clear_user':
      return {
        icon: 'fa-broom',
        text: html`Los mensajes de <strong>${data.display_name}</strong> fueron eliminados por un moderador.`,
        className: 'sys-mod',
      };
    case 'twitch_message_delete':
      return {
        icon: 'fa-eraser',
        text: html`Se eliminó un mensaje de <strong>${data.display_name}</strong>.`,
        className: 'sys-mod',
      };
    default:
      return {
        icon: 'fa-bell',
        text: 'Alerta del sistema recibida.',
        className: 'sys-default',
      };
  }
}

// Mensaje de chat
function ChatMessage({ msg }) {
  if (msg.isSystem) {
    const details = getSystemMessageDetails(msg);
    return html`
      <div class="chat-msg is-system ${details.className}">
        <span class="chat-time">${fmtTime(msg.timestamp)}</span>
        <span class="sys-icon"><i class="fa-solid ${details.icon}"></i></span>
        <span class="sys-text">${details.text}</span>
      </div>
    `;
  }

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
  const timeStr = user.timestamp ? fmtTime(user.timestamp) : '--:--';
  const nameStr = user.display_name || user.username;
  
  let followStatus = '';
  if (user.role === 'Broadcaster') {
    followStatus = '[Broadcaster]';
  } else if (user.role === 'Bot' || user.is_bot) {
    followStatus = '[Bot]';
  } else if (user.role && user.role !== 'Visita' && user.role !== 'Desconocido') {
    followStatus = `[${user.role}]`;
  } else {
    followStatus = '[Visita]';
  }

  const badges = [];
  if (user.is_moderator) {
    badges.push(html`<span class="irc-badge badge-moderator">Mod</span>`);
  }
  if (user.is_vip) {
    badges.push(html`<span class="irc-badge badge-vip">VIP</span>`);
  }
  if (user.is_subscriber) {
    badges.push(html`<span class="irc-badge badge-subscriber">Sub</span>`);
  }

  return html`
    <div class="irc-user">
      <div class="irc-user-main">
        <span class="irc-time">{${timeStr}}</span>
        <span class="irc-name" style="color:${color}">${nameStr}</span>
        <div class="irc-user-badges">
          ${badges}
        </div>
      </div>
      <div class="irc-user-sub">
        ${user.nickname && user.nickname !== nameStr
          ? html`<span class="irc-nickname">(${user.nickname})</span>`
          : null
        }
        <span class="irc-follow-status">${followStatus}</span>
      </div>
    </div>
  `;
}

export function ChatTab({ chatMessages, ircUsers, showIrcMobile, onToggleIrc }) {
  const feedRef = useRef(null);
  const autoScrollRef = useRef(true);
  const [isAtBottom, setIsAtBottom] = useState(true);

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
    setIsAtBottom(atBottom);
    autoScrollRef.current = atBottom;
  }

  function scrollToBottom() {
    const el = feedRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    setIsAtBottom(true);
    autoScrollRef.current = true;
  }

  const users = [...ircUsers.values()]
    .filter(u => u.role !== 'Broadcaster' && !u.is_bot && u.role !== 'Bot')
    .sort((a, b) =>
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
        
        <div class="chat-feed-container" style="position:relative;flex:1;min-height:0;display:flex;flex-direction:column">
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

          <!-- Botón de scroll al final -->
          ${!isAtBottom && chatMessages.length > 0 ? html`
            <button class="scroll-bottom-btn" onClick=${scrollToBottom}>
              <i class="fa-solid fa-arrow-down"></i> Mensajes nuevos
            </button>
          ` : null}
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
