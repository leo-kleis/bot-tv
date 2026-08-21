import { html, useEffect, useRef, useState, useMemo } from 'preact-setup';
import { getEventDetails } from '../event-config.js';
import { toRgb, fmtTime } from 'lib/utils';
import { apiGet, apiPost } from '../api.js';
import { CustomSelect } from '../CustomSelect.js';
import { UserAvatar } from '../UserAvatar.js';
import { ChatHeaderButton } from './ChatHeaderButton.js';
import { ContextMenu } from '../ContextMenu.js';
import { ConfirmModal } from '../ConfirmModal.js';
import { UserProfileDrawer } from '../user/UserProfileDrawer.js';
import { fetchEmotes, parseEmotes } from '/static/lib/emotes.js';

function roleDisplay(role) {
  if (!role || role === 'Visita') return 'Visita';
  return role;
}

// Encabezado de grupo: avatar + nombre + rol + hora + texto del primer mensaje
function ChatMessageGroup({ msg, emotesMap, onUserClick, onMsgContext }) {
  const color = toRgb(msg.color_rgb);
  const rLabel = roleDisplay(msg.role);

  return html`
    <div
      class="chat-msg-group ${msg.is_bot ? 'is-bot' : ''}"
      onContextMenu=${e => onMsgContext(e, msg)}
    >
      <div onClick=${e => onUserClick(e, msg)} style="cursor:pointer;">
        <${UserAvatar}
          userId=${msg.user_id}
          displayName=${msg.display_name}
          color=${color}
          size="md"
        />
      </div>
      <div class="chat-msg-content">
        <div class="chat-msg-header">
          <span
            class="chat-author"
            style="color:${color}; cursor:pointer;"
            onClick=${e => onUserClick(e, msg)}
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
}

// Mensaje continuación: solo texto, hora visible en hover
function ChatMessageCont({ msg, emotesMap, onMsgContext }) {
  return html`
    <div
      class="chat-msg-cont ${msg.is_bot ? 'is-bot' : ''}"
      onContextMenu=${e => onMsgContext(e, msg)}
    >
      <span class="chat-time-hover">${fmtTime(msg.timestamp)}</span>
      <div class="chat-msg-body">${parseEmotes(msg.text, emotesMap, msg.emotes)}</div>
    </div>
  `;
}

// Mensaje de sistema
function ChatMessageSystem({ msg }) {
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

// Usuario IRC
function IrcUser({ user, onUserClick }) {
  const color = toRgb(user.color_rgb);
  const timeStr = user.timestamp ? fmtTime(user.timestamp) : '--:--';
  const nameStr = user.display_name || user.username;
  const isParted = user.present === false;

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
    const label =
      user.sub_tier === '3000' ? 'Sub T3' : user.sub_tier === '2000' ? 'Sub T2' : 'Sub T1';
    badges.push(html`<span class="irc-badge badge-subscriber">${label}</span>`);
  }

  const metaText = user.nickname ? `${user.nickname} · ${followStatus}` : followStatus;

  return html`
    <div
      class="irc-user ${isParted ? 'is-parted' : ''}"
      onClick=${e => onUserClick(e, user)}
      style="cursor:pointer;"
    >
      <${UserAvatar} userId=${user.user_id} displayName=${nameStr} color=${color} size="md" />
      <div class="irc-user-details">
        <div class="irc-user-top">
          <span class="irc-name" style="color:${color}">${nameStr}</span>
          ${badges.length > 0 ? html`<div class="irc-user-badges">${badges}</div>` : null}
        </div>
        <div class="irc-user-bottom">
          <span class="irc-meta">${metaText}</span>
          <span class="irc-time">${timeStr}</span>
        </div>
      </div>
    </div>
  `;
}

export function ChatTab({
  chatMessages,
  ircUsers,
  ircConnected,
  showIrcMobile,
  onToggleIrc,
  dispatch,
  streamOnline = false,
}) {
  const feedRef = useRef(null);
  const inputRef = useRef(null);
  const autoScrollRef = useRef(true);
  const timeoutsRef = useRef([]);
  const [isAtBottom, setIsAtBottom] = useState(true);

  // Estados de cuentas y mensajería
  const [accounts, setAccounts] = useState([]);
  const [selectedSenderId, setSelectedSenderId] = useState('');
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [clipping, setClipping] = useState(false);
  const [clearingChat, setClearingChat] = useState(false);
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);

  // Perfil de usuario y Menú Contextual
  const [profileUser, setProfileUser] = useState(null);
  const [contextMenu, setContextMenu] = useState(null); // { position: {x,y}, items: [...] }

  const [emotesMap, setEmotesMap] = useState({});
  const [hideBots, setHideBots] = useState(
    () => localStorage.getItem('hide-bot-messages') === 'true'
  );

  useEffect(() => {
    function handleStorageUpdate() {
      setHideBots(localStorage.getItem('hide-bot-messages') === 'true');
    }
    window.addEventListener('storage-settings-changed', handleStorageUpdate);
    return () => window.removeEventListener('storage-settings-changed', handleStorageUpdate);
  }, []);

  const displayMessages = useMemo(() => {
    if (!hideBots) return chatMessages;
    return chatMessages.filter(m => m.isSystem || (!m.is_bot && m.role !== 'Bot'));
  }, [chatMessages, hideBots]);

  // Handler para crear Clip
  async function handleCreateClip() {
    if (clipping || !streamOnline) return;
    setClipping(true);
    try {
      const data = await apiPost('/api/create_clip', {});
      if (!data.ok && dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'api_error',
            data: { message: data.error || 'No se pudo crear el clip.' },
          },
        });
      }
    } catch {}
    setClipping(false);
  }

  // Handler para limpiar chat público (/clear)
  async function handleExecuteClearChat() {
    setClearingChat(true);
    setConfirmClearOpen(false);
    try {
      const res = await apiPost('/api/moderation/delete_message', {});
      if (res.ok && dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'mod_action',
            data: { message: 'Sala de chat limpiada en Twitch.' },
          },
        });
      } else if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'api_error',
            data: { message: res.error || 'No se pudo limpiar la sala de chat.' },
          },
        });
      }
    } catch (e) {
      console.error(e);
    }
    setClearingChat(false);
  }

  // Cargar las cuentas autenticadas
  useEffect(() => {
    async function loadAccounts() {
      const res = await apiGet('/api/chat_accounts');
      if (res.ok && Array.isArray(res.data)) {
        setAccounts(res.data);
        if (res.data.length > 0) {
          const broadcasterAcc = res.data.find(acc => acc.type === 'broadcaster');
          const finalSenderId = broadcasterAcc ? broadcasterAcc.user_id : res.data[0].user_id;
          setSelectedSenderId(finalSenderId);

          try {
            const loaded = await fetchEmotes(finalSenderId);
            setEmotesMap(loaded);
          } catch (e) {
            console.error('Error al cargar emotes:', e);
          }
        }
      }
    }
    loadAccounts();
  }, []);

  // Limpiar timeouts al desmontar
  useEffect(() => {
    return () => {
      timeoutsRef.current.forEach(clearTimeout);
    };
  }, []);

  // Auto-scroll solo si el usuario no subió manualmente
  useEffect(() => {
    const el = feedRef.current;
    if (!el || !autoScrollRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [displayMessages]);

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
        const tid = setTimeout(() => {
          dispatch({ type: 'REMOVE_TOAST', id: toastId });
          timeoutsRef.current = timeoutsRef.current.filter(t => t !== tid);
        }, 5000);
        timeoutsRef.current.push(tid);
      }
    }

    const focusTid = setTimeout(() => {
      inputRef.current?.focus();
      timeoutsRef.current = timeoutsRef.current.filter(t => t !== focusTid);
    }, 50);
    timeoutsRef.current.push(focusTid);
  }

  // Abrir perfil de usuario desde clic o menú contextual
  function handleOpenUserProfile(userData) {
    setProfileUser({
      user_id: userData.user_id,
      username: userData.username || userData.name || userData.display_name,
      display_name: userData.display_name || userData.username,
      nickname: userData.nickname || null,
      is_bot: !!userData.is_bot,
      is_moderator: !!userData.is_moderator,
      is_vip: !!userData.is_vip,
      is_subscriber: !!userData.is_subscriber,
    });
  }

  // Manejar Menú Contextual en un Mensaje de Chat
  function handleMsgContextMenu(e, msg) {
    e.preventDefault();
    const uName = msg.display_name || msg.username || 'usuario';

    const items = [
      {
        label: `Ver perfil de ${uName}`,
        icon: 'fa-user-gear',
        onClick: () => handleOpenUserProfile(msg),
      },
    ];

    if (msg.id) {
      items.push({
        label: 'Eliminar este mensaje',
        icon: 'fa-trash-can',
        isDanger: true,
        onClick: async () => {
          const res = await apiPost('/api/moderation/delete_message', {
            username: msg.username || msg.display_name,
            message_id: msg.id,
          });
          if (res.ok && dispatch) {
            dispatch({
              type: 'ADD_TOAST',
              toast: {
                id: Date.now().toString(),
                type: 'mod_action',
                data: { message: 'Mensaje eliminado de Twitch.' },
              },
            });
          }
        },
      });
    }

    setContextMenu({
      position: { x: e.clientX || e.pageX, y: e.clientY || e.pageY },
      items,
    });
  }

  const users = useMemo(() => {
    return [...ircUsers.values()]
      .filter(u => u.role !== 'Broadcaster' && !u.is_bot && u.role !== 'Bot')
      .sort((a, b) => {
        const aPresent = a.present !== false;
        const bPresent = b.present !== false;

        if (aPresent !== bPresent) {
          return aPresent ? -1 : 1;
        }

        if (aPresent && bPresent) {
          const aTime = a.joinedAt || a.timestamp || '';
          const bTime = b.joinedAt || b.timestamp || '';
          return aTime.localeCompare(bTime);
        }

        const aPartTime = a.partedAt || a.timestamp || '';
        const bPartTime = b.partedAt || b.timestamp || '';
        return bPartTime.localeCompare(aPartTime);
      });
  }, [ircUsers]);

  return html`
    <div class="chat-tab ${showIrcMobile ? 'irc-open-mobile' : ''}">
      <!-- Panel Chat (izquierda) -->
      <div class="chat-panel">
        <div class="chat-panel-header">
          <div style="display:flex;align-items:center;gap:8px;min-width:0;">
            <span>Chat</span>
            <span style="color:var(--text-muted);font-size:10px">${chatMessages.length} msgs</span>
          </div>
          <div style="display:flex;gap:8px;min-width:0;">
            <${ChatHeaderButton}
              id="btn-chat-clear"
              icon="fa-broom"
              label="Limpiar Chat"
              title="Borrar sala de chat pública (/clear)"
              disabled=${clearingChat}
              loading=${clearingChat}
              onClick=${() => setConfirmClearOpen(true)}
            />
            <${ChatHeaderButton}
              id="btn-chat-clip"
              icon="fa-scissors"
              label="Clip"
              title=${!streamOnline ? 'El canal debe estar en vivo para clipear' : 'Crear clip (F6)'}
              disabled=${clipping || !streamOnline}
              loading=${clipping}
              onClick=${handleCreateClip}
            />
          </div>
        </div>

        <div
          class="chat-feed-container"
          style="position:relative;flex:1;min-height:0;display:flex;flex-direction:column"
        >
          <div
            class="chat-feed"
            ref=${feedRef}
            onScroll=${onScroll}
            id="chat-feed"
            role="log"
            aria-live="polite"
            aria-relevant="additions"
          >
            ${
              displayMessages.length === 0
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
                : displayMessages.map((m, i) => {
                    if (m.isSystem) {
                      return html`<${ChatMessageSystem} key=${m.timestamp + i} msg=${m} />`;
                    }
                    const prev = displayMessages[i - 1];
                    const isGrouped = prev && !prev.isSystem && prev.user_id === m.user_id;
                    return isGrouped
                      ? html`<${ChatMessageCont}
                          key=${m.timestamp + i}
                          msg=${m}
                          emotesMap=${emotesMap}
                          onMsgContext=${handleMsgContextMenu}
                        />`
                      : html`<${ChatMessageGroup}
                          key=${m.timestamp + i}
                          msg=${m}
                          emotesMap=${emotesMap}
                          onUserClick=${(e, uData) => handleOpenUserProfile(uData)}
                          onMsgContext=${handleMsgContextMenu}
                        />`;
                  })
            }
          </div>

          <!-- Botón de scroll al final -->
          ${
            !isAtBottom && displayMessages.length > 0
              ? html`
                  <button class="scroll-bottom-btn" onClick=${scrollToBottom}>
                    <i class="fa-solid fa-arrow-down"></i> Mensajes nuevos
                  </button>
                `
              : null
          }
        </div>

        <!-- Caja de Texto para Enviar Mensaje -->
        <div class="chat-input-container">
          <form onSubmit=${handleSend} class="chat-input-form">
            ${
              accounts.length > 0
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
                : null
            }
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
              ${
                sending
                  ? html`<i class="fa-solid fa-spinner fa-spin"></i>`
                  : html`<i class="fa-solid fa-paper-plane"></i>`
              }
            </button>
          </form>
        </div>
      </div>

      <!-- Overlay móvil -->
      ${
        showIrcMobile
          ? html`<div class="irc-overlay-mobile" onClick=${() => onToggleIrc(false)}></div>`
          : null
      }

      <!-- Panel IRC Usuarios (derecha) -->
      <div class="irc-panel">
        <div class="irc-panel-header">
          <span>En canal</span>
          ${
            !ircConnected &&
            html`
              <span class="irc-status-warning" title="IRC Desconectado (Reintentando...)">
                <i class="fa-solid fa-triangle-exclamation"></i>
              </span>
            `
          }
        </div>

        <div class="irc-feed" id="irc-feed">
          ${
            !ircConnected &&
            html`
              <div class="irc-disconnect-alert">
                <span class="alert-icon"><i class="fa-solid fa-triangle-exclamation"></i></span>
                <span class="alert-title">IRC Desconectado</span>
                <span class="alert-desc">Intentando reconectar automáticamente...</span>
              </div>
            `
          }
          ${
            users.length === 0
              ? !ircConnected
                ? null
                : html`
                    <div
                      style="padding:16px 10px;color:var(--text-muted);font-size:11px;text-align:center"
                    >
                      Vacío
                    </div>
                  `
              : users.map(
                  u => html`
                    <${IrcUser}
                      key=${u.user_id || u.username}
                      user=${u}
                      onUserClick=${(e, uData) => handleOpenUserProfile(uData)}
                    />
                  `
                )
          }
        </div>
      </div>
    </div>

    <!-- Menú Contextual Flotante -->
    ${
      contextMenu
        ? html`<${ContextMenu}
            position=${contextMenu.position}
            items=${contextMenu.items}
            onClose=${() => setContextMenu(null)}
          />`
        : null
    }

    <!-- Drawer Unificado de Perfil de Usuario -->
    ${
      profileUser
        ? html`<${UserProfileDrawer}
            user=${profileUser}
            onClose=${() => setProfileUser(null)}
            dispatch=${dispatch}
          />`
        : null
    }

    <!-- Modal Confirmación Limpieza Chat Global (/clear) -->
    <${ConfirmModal}
      isOpen=${confirmClearOpen}
      title="¿Limpiar el chat?"
      message="Se borrarán los mensajes visibles en Twitch."
      confirmText="Confirmar limpieza"
      isDanger=${true}
      onConfirm=${handleExecuteClearChat}
      onClose=${() => setConfirmClearOpen(false)}
    />
  `;
}
