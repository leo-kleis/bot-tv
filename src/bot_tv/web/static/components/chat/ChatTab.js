import { html, useEffect, useState, useMemo, useCallback } from 'preact-setup';
import { apiGet, apiPost } from '../api.js';
import { ChatHeaderButton } from './ChatHeaderButton.js';
import { ChatFeed } from './ChatFeed.js';
import { ChatInputBar } from './ChatInputBar.js';
import { IrcUsersPanel } from './IrcUsersPanel.js';
import { ContextMenu } from '../ContextMenu.js';
import { ConfirmModal } from '../ConfirmModal.js';
import { DisplaySettingsMenu } from '../DisplaySettingsMenu.js';
import { UserProfileDrawer } from '../user/UserProfileDrawer.js';
import { fetchEmotes } from '/static/lib/emotes.js';

/** @typedef {import('/static/lib/emotes.js').EmotesMap} EmotesMap */
/** @typedef {import('/static/state/types.js').AppDispatch} AppDispatch */
/** @typedef {import('/static/state/types.js').ChatEntry} ChatEntry */
/** @typedef {import('/static/state/types.js').ChatMessage} ChatMessage */
/** @typedef {import('/static/state/types.js').IrcUser} IrcUser */
/** @typedef {import('/static/state/types.js').IrcUsersMap} IrcUsersMap */

/**
 * @typedef {Object} ProfileUserSelection
 * @property {string | undefined} user_id
 * @property {string} username
 * @property {string} display_name
 * @property {string | null} nickname
 * @property {boolean} is_bot
 * @property {boolean} is_moderator
 * @property {boolean} is_vip
 * @property {boolean} is_subscriber
 */

/**
 * @typedef {Object} ContextMenuState
 * @property {{ x: number, y: number }} position
 * @property {Array<{ label: string, icon?: string, isDanger?: boolean, onClick: () => void | Promise<void> }>} items
 */

/**
 * Pestaña principal de chat en vivo, barra de envío y panel de usuarios IRC.
 *
 * @param {Object} props
 * @param {ChatEntry[]} props.chatMessages
 * @param {IrcUsersMap} props.ircUsers
 * @param {boolean} props.ircConnected
 * @param {boolean} props.showIrcMobile
 * @param {(open: boolean) => void} props.onToggleIrc
 * @param {AppDispatch} props.dispatch
 * @param {boolean} [props.streamOnline=false]
 */
export function ChatTab({
  chatMessages,
  ircUsers,
  ircConnected,
  showIrcMobile,
  onToggleIrc,
  dispatch,
  streamOnline = false,
}) {
  const [accounts, setAccounts] = useState(
    /** @type {Array<{ user_id: string, username: string, type: string }>} */ ([])
  );
  const [selectedSenderId, setSelectedSenderId] = useState('');
  const [clipping, setClipping] = useState(false);
  const [clearingChat, setClearingChat] = useState(false);
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);

  /** @type {[ProfileUserSelection | null, (u: ProfileUserSelection | null) => void]} */
  const [profileUser, setProfileUser] = useState(null);
  /** @type {[ContextMenuState | null, (menu: ContextMenuState | null) => void]} */
  const [contextMenu, setContextMenu] = useState(null);

  /** @type {[EmotesMap, (map: EmotesMap) => void]} */
  const [emotesMap, setEmotesMap] = useState({});
  const [hideBots, setHideBots] = useState(
    () => localStorage.getItem('hide-bot-messages') === 'true'
  );

  useEffect(() => {
    function handleStorageUpdate() {
      setHideBots(localStorage.getItem('hide-bot-messages') === 'true');
    }
    window.addEventListener('storage-settings-changed', handleStorageUpdate);
    window.addEventListener('storage', handleStorageUpdate);
    return () => {
      window.removeEventListener('storage-settings-changed', handleStorageUpdate);
      window.removeEventListener('storage', handleStorageUpdate);
    };
  }, []);

  const displayMessages = useMemo(() => {
    if (!hideBots) return chatMessages;
    return chatMessages.filter(m => m.isSystem || (!m.is_bot && m.role !== 'Bot'));
  }, [chatMessages, hideBots]);

  // Handler para crear Clip
  const handleCreateClip = useCallback(async () => {
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
    } catch {
      // Ignorar errores de red transitorios
    }
    setClipping(false);
  }, [clipping, streamOnline, dispatch]);

  // Atajo F6 para crear clip cuando el stream está en vivo
  useEffect(() => {
    /** @param {KeyboardEvent} e */
    function handleClipShortcut(e) {
      if (e.key === 'F6' && streamOnline && !clipping) {
        e.preventDefault();
        handleCreateClip();
      }
    }
    window.addEventListener('keydown', handleClipShortcut);
    return () => window.removeEventListener('keydown', handleClipShortcut);
  }, [streamOnline, clipping, handleCreateClip]);

  // Handler para limpiar chat público (/clear)
  const handleExecuteClearChat = useCallback(async () => {
    setClearingChat(true);
    setConfirmClearOpen(false);
    try {
      const res = await apiPost('/api/moderation/delete_message', { clear_all: true });
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
  }, [dispatch]);

  // Cargar las cuentas autenticadas y emotes del canal
  useEffect(() => {
    let cancelled = false;

    async function loadAccounts() {
      const res = await apiGet('/api/chat_accounts');
      if (cancelled) return;

      if (res.ok && Array.isArray(res.data)) {
        setAccounts(res.data);
        if (res.data.length > 0) {
          const broadcasterAcc = res.data.find(
            /** @param {{ type: string }} acc */ acc => acc.type === 'broadcaster'
          );
          const finalSenderId = broadcasterAcc ? broadcasterAcc.user_id : res.data[0].user_id;
          setSelectedSenderId(finalSenderId);

          try {
            const loaded = await fetchEmotes(finalSenderId);
            if (!cancelled) {
              setEmotesMap(loaded);
            }
          } catch (e) {
            console.error('Error al cargar emotes:', e);
          }
        }
      }
    }

    loadAccounts();
    return () => {
      cancelled = true;
    };
  }, []);

  // Abrir perfil de usuario desde clic o menú contextual
  const handleOpenUserProfile = useCallback(
    /** @param {ChatMessage | IrcUser} userData */
    userData => {
      const resolvedUsername = userData.username || userData.display_name || 'usuario';
      setProfileUser({
        user_id: userData.user_id,
        username: resolvedUsername,
        display_name: userData.display_name || resolvedUsername,
        nickname: userData.nickname || null,
        is_bot: Boolean(userData.is_bot),
        is_moderator: Boolean(userData.is_moderator),
        is_vip: Boolean(userData.is_vip),
        is_subscriber: Boolean(userData.is_subscriber),
      });
    },
    []
  );

  // Manejar Menú Contextual en un Mensaje de Chat
  const handleMsgContextMenu = useCallback(
    /**
     * @param {MouseEvent} e
     * @param {ChatMessage} msg
     */
    (e, msg) => {
      e.preventDefault();
      const uName = msg.display_name || msg.username || 'usuario';

      /** @type {ContextMenuState['items']} */
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
    },
    [dispatch, handleOpenUserProfile]
  );

  const handleOpenConfirmClear = useCallback(() => setConfirmClearOpen(true), []);
  const handleCloseConfirmClear = useCallback(() => setConfirmClearOpen(false), []);
  const handleCloseContextMenu = useCallback(() => setContextMenu(null), []);
  const handleCloseProfile = useCallback(() => setProfileUser(null), []);

  return html`
    <div class="chat-tab ${showIrcMobile ? 'irc-open-mobile' : ''}">
      <div class="chat-panel">
        <div class="chat-panel-header">
          <div style="display:flex;align-items:center;gap:8px;min-width:0;">
            <span>Chat</span>
            <span style="color:var(--text-muted);font-size:11px">${chatMessages.length} msgs</span>
          </div>
          <div style="display:flex;gap:8px;min-width:0;">
            <${ChatHeaderButton}
              id="btn-chat-clear"
              icon="fa-broom"
              label="Limpiar Chat"
              title="Borrar sala de chat pública (/clear)"
              disabled=${clearingChat}
              loading=${clearingChat}
              onClick=${handleOpenConfirmClear}
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
            <${DisplaySettingsMenu} showHideBots=${true} buttonId="chat-display-btn" />
          </div>
        </div>

        <${ChatFeed}
          displayMessages=${displayMessages}
          emotesMap=${emotesMap}
          onUserClick=${handleOpenUserProfile}
          onMsgContext=${handleMsgContextMenu}
        />

        <${ChatInputBar}
          accounts=${accounts}
          selectedSenderId=${selectedSenderId}
          onSelectSender=${setSelectedSenderId}
          dispatch=${dispatch}
        />
      </div>

      <${IrcUsersPanel}
        ircUsers=${ircUsers}
        ircConnected=${ircConnected}
        showIrcMobile=${showIrcMobile}
        onToggleIrc=${onToggleIrc}
        onUserClick=${handleOpenUserProfile}
      />
    </div>

    ${
      contextMenu
        ? html`<${ContextMenu}
            position=${contextMenu.position}
            items=${contextMenu.items}
            onClose=${handleCloseContextMenu}
          />`
        : null
    }
    ${
      profileUser
        ? html`<${UserProfileDrawer}
            user=${profileUser}
            onClose=${handleCloseProfile}
            dispatch=${dispatch}
          />`
        : null
    }

    <${ConfirmModal}
      isOpen=${confirmClearOpen}
      title="¿Limpiar el chat?"
      message="Se borrarán los mensajes visibles en Twitch."
      confirmText="Confirmar limpieza"
      isDanger=${true}
      onConfirm=${handleExecuteClearChat}
      onClose=${handleCloseConfirmClear}
    />
  `;
}
