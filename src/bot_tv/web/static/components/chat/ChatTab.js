import { html, useEffect, useRef, useState } from 'preact-setup';
import { getEventDetails } from '../event-config.js';
import { toRgb, fmtTime } from 'lib/utils';
import { apiGet, apiPost } from '../api.js';
import { CustomSelect } from '../CustomSelect.js';

function roleDisplay(role) {
  if (!role || role === 'Visita') return 'Visita';
  return role;
}

// Mensaje de chat
function ChatMessage({ msg }) {
  if (msg.isSystem) {
    const details = getEventDetails(msg.type);
    const textHtml = details.chatHtml(msg.data, html);
    return html`
      <div class="chat-msg is-system ${details.sysClassName}">
        <span class="chat-time">${fmtTime(msg.timestamp)}</span>
        <span class="sys-icon"><i class="fa-solid ${details.icon}"></i></span>
        <span class="sys-text">${textHtml}</span>
      </div>
    `;
  }

  const color = toRgb(msg.color_rgb);
  const rLabel = roleDisplay(msg.role);

  return html`
    <div class="chat-msg ${msg.is_bot ? 'is-bot' : ''}">
      <span class="chat-time">${fmtTime(msg.timestamp)}</span>
      <span class="chat-author" style="color:${color}">
        ${msg.nickname
          ? html`<span class="chat-nickname">${msg.nickname}</span
              ><span class="chat-display"> ${msg.display_name}</span>`
          : html`<span class="chat-nickname">${msg.display_name}</span>`}
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
        <div class="irc-user-badges">${badges}</div>
      </div>
      <div class="irc-user-sub">
        ${user.nickname && user.nickname !== nameStr
          ? html`<span class="irc-nickname">(${user.nickname})</span>`
          : null}
        <span class="irc-follow-status">${followStatus}</span>
      </div>
    </div>
  `;
}

export function ChatTab({ chatMessages, ircUsers, showIrcMobile, onToggleIrc, dispatch }) {
  const feedRef = useRef(null);
  const inputRef = useRef(null);
  const autoScrollRef = useRef(true);
  const [isAtBottom, setIsAtBottom] = useState(true);

  // Estados para cuentas y mensajería
  const [accounts, setAccounts] = useState([]);
  const [selectedSenderId, setSelectedSenderId] = useState('');
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);

  // Cargar las cuentas autenticadas
  useEffect(() => {
    async function loadAccounts() {
      const res = await apiGet('/api/chat_accounts');
      if (res.ok && Array.isArray(res.data)) {
        setAccounts(res.data);
        if (res.data.length > 0) {
          // Seleccionar broadcaster por defecto si existe, sino la primera
          const broadcasterAcc = res.data.find(acc => acc.type === 'broadcaster');
          setSelectedSenderId(broadcasterAcc ? broadcasterAcc.user_id : res.data[0].user_id);
        }
      }
    }
    loadAccounts();
  }, []);

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

  async function handleSend(e) {
    if (e) e.preventDefault();
    if (!inputText.trim() || !selectedSenderId || sending) return;

    setSending(true);
    const messageText = inputText;

    const res = await apiPost('/api/send_chat_message', {
      sender_id: selectedSenderId,
      message: messageText,
    });

    setSending(false);

    if (res.ok) {
      setInputText('');
    } else {
      if (dispatch) {
        const toastId = Date.now().toString() + Math.random().toString(36).substr(2, 9);
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: toastId,
            type: 'api_error',
            data: { message: `No se pudo enviar: ${res.error || 'error desconocido'}` },
          },
        });
        setTimeout(() => {
          dispatch({ type: 'REMOVE_TOAST', id: toastId });
        }, 5000);
      }
    }

    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
  }

  const users = [...ircUsers.values()]
    .filter(u => u.role !== 'Broadcaster' && !u.is_bot && u.role !== 'Bot')
    .sort((a, b) => (a.display_name || a.username).localeCompare(b.display_name || b.username));

  return html`
    <div class="chat-tab ${showIrcMobile ? 'irc-open-mobile' : ''}">
      <!-- Panel Chat (izquierda) -->
      <div class="chat-panel">
        <div class="chat-panel-header">
          <span>Chat</span>
          <span style="color:var(--text-muted);font-size:10px">${chatMessages.length} msgs</span>
        </div>

        <div
          class="chat-feed-container"
          style="position:relative;flex:1;min-height:0;display:flex;flex-direction:column"
        >
          <div class="chat-feed" ref=${feedRef} onScroll=${onScroll} id="chat-feed">
            ${chatMessages.length === 0
              ? html`
                  <div class="chat-empty">
                    <span class="empty-icon"
                      ><i
                        class="fa-regular fa-comments fa-3x"
                        style="color:var(--text-muted);margin-bottom:12px"
                      ></i
                    ></span>
                    <span>Esperando mensajes...</span>
                  </div>
                `
              : chatMessages.map(
                  (m, i) => html`<${ChatMessage} key=${m.timestamp + i} msg=${m} />`
                )}
          </div>

          <!-- Botón de scroll al final -->
          ${!isAtBottom && chatMessages.length > 0
            ? html`
                <button class="scroll-bottom-btn" onClick=${scrollToBottom}>
                  <i class="fa-solid fa-arrow-down"></i> Mensajes nuevos
                </button>
              `
            : null}
        </div>

        <!-- Caja de Texto para Enviar Mensaje (Bot/Broadcaster) -->
        <div class="chat-input-container">
          <form onSubmit=${handleSend} class="chat-input-form">
            ${accounts.length > 0
              ? html`
                  <${CustomSelect}
                    className="chat-select-field"
                    value=${selectedSenderId}
                    onChange=${setSelectedSenderId}
                    disabled=${sending}
                    options=${accounts.map(acc => ({
                      value: acc.user_id,
                      label: `${acc.username} (${acc.type === 'bot' ? 'Bot' : 'Broadcaster'})`,
                    }))}
                  />
                `
              : null}
            <input
              type="text"
              class="chat-input-field"
              ref=${inputRef}
              placeholder="Escribe un mensaje al chat..."
              value=${inputText}
              onInput=${e => setInputText(e.target.value)}
              disabled=${sending}
            />
            <button
              type="submit"
              class="chat-send-btn"
              disabled=${!inputText.trim() || sending || !selectedSenderId}
            >
              ${sending
                ? html`<i class="fa-solid fa-spinner fa-spin"></i>`
                : html`<i class="fa-solid fa-paper-plane"></i>`}
            </button>
          </form>
        </div>
      </div>

      <!-- Overlay móvil -->
      ${showIrcMobile
        ? html`<div class="irc-overlay-mobile" onClick=${() => onToggleIrc(false)}></div>`
        : null}

      <!-- Panel IRC Usuarios (derecha) -->
      <div class="irc-panel">
        <div class="irc-panel-header">
          <span>En canal</span>
          <span class="irc-count">${users.length}</span>
        </div>
        <div class="irc-feed" id="irc-feed">
          ${users.length === 0
            ? html`
                <div
                  style="padding:16px 10px;color:var(--text-muted);font-size:11px;text-align:center"
                >
                  Vacío
                </div>
              `
            : users.map(u => html`<${IrcUser} key=${u.username} user=${u} />`)}
        </div>
      </div>
    </div>
  `;
}
