import { html, useState, useEffect, useRef } from 'preact-setup';
import { apiGet, apiPost } from '/static/components/api.js';
import { ConfirmModal } from '/static/components/ConfirmModal.js';
import { useMessageHistory, formatCount } from '/static/hooks/useMessageHistory.js';
import { getFocusableElements, trapFocus, setupInertIsolation } from '/static/lib/a11y.js';
import { UserInfoTabPanel, UserRolesTabPanel, UserHistoryTabPanel } from './UserProfileTabs.js';

const TAB_IDS = ['info', 'roles', 'history'];

export function UserProfileDrawer({ user, onClose, dispatch }) {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('info'); // 'info', 'roles', 'history'

  // Datos del usuario local & roles
  const [userData, setUserData] = useState(user || {});
  const [nickname, setNickname] = useState(user?.nickname || '');
  const [editingNick, setEditingNick] = useState(false);
  const [savingNick, setSavingNick] = useState(false);
  const [nickError, setNickError] = useState(null);

  const [tempRoles, setTempRoles] = useState({
    is_bot: !!user?.is_bot,
    is_moderator: !!user?.is_moderator,
    is_vip: !!user?.is_vip,
    is_subscriber: !!user?.is_subscriber,
  });
  const [syncingRoles, setSyncingRoles] = useState(false);
  const [savingRoles, setSavingRoles] = useState(false);
  const [rolesError, setRolesError] = useState(null);
  const [modError, setModError] = useState(null);

  // Modales de Confirmación de Moderación
  const [confirmBanOpen, setConfirmBanOpen] = useState(false);
  const [confirmUnbanOpen, setConfirmUnbanOpen] = useState(false);
  const [confirmPurgeOpen, setConfirmPurgeOpen] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);

  // Filtros de historial de mensajes
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');
  const messagesRef = useRef(null);
  const prevScrollHeightRef = useRef(0);
  const drawerRef = useRef(null);
  const triggerRef = useRef(null);
  const restoreInertRef = useRef(null);
  const closeTimerRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const isClosingRef = useRef(false);

  const confirmBanOpenRef = useRef(confirmBanOpen);
  confirmBanOpenRef.current = confirmBanOpen;
  const confirmUnbanOpenRef = useRef(confirmUnbanOpen);
  confirmUnbanOpenRef.current = confirmUnbanOpen;
  const confirmPurgeOpenRef = useRef(confirmPurgeOpen);
  confirmPurgeOpenRef.current = confirmPurgeOpen;

  const hasSyncedRoles = useRef(false);

  const username = user ? user.username || user.display_name : '';
  const displayName = userData.display_name || user?.display_name || username;

  function scheduleCloseCallback() {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
    }
    closeTimerRef.current = setTimeout(() => {
      closeTimerRef.current = null;
      if (onCloseRef.current) onCloseRef.current();
    }, 300);
  }

  function handleClose() {
    if (isClosingRef.current) return;
    isClosingRef.current = true;
    setOpen(false);
    if (restoreInertRef.current) {
      restoreInertRef.current();
      restoreInertRef.current = null;
    }
    if (window.history.state && window.history.state.botDrawer === 'user-profile') {
      window.history.back();
    }
    scheduleCloseCallback();
  }

  function handlePopState() {
    if (isClosingRef.current) return;
    isClosingRef.current = true;
    setOpen(false);
    if (restoreInertRef.current) {
      restoreInertRef.current();
      restoreInertRef.current = null;
    }
    scheduleCloseCallback();
  }

  function handleTabKeyDown(e, currentTabId) {
    let nextTabId = null;
    const currentIndex = TAB_IDS.indexOf(currentTabId);
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextTabId = TAB_IDS[(currentIndex + 1) % TAB_IDS.length];
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextTabId = TAB_IDS[(currentIndex - 1 + TAB_IDS.length) % TAB_IDS.length];
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextTabId = TAB_IDS[0];
    } else if (e.key === 'End') {
      e.preventDefault();
      nextTabId = TAB_IDS[TAB_IDS.length - 1];
    }

    if (nextTabId) {
      setActiveTab(nextTabId);
      const nextBtn = document.getElementById(`drawer-tab-${nextTabId}`);
      if (nextBtn) nextBtn.focus();
    }
  }

  // Cargar datos consolidados de usuario (follow, roles, etc.) al abrir el drawer
  useEffect(() => {
    if (!username) return;
    const controller = new AbortController();

    async function loadUserDetails() {
      try {
        const res = await apiGet(`/api/users/${encodeURIComponent(username)}/detail`, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        if (res && res.ok && res.data) {
          setUserData(prev => ({
            ...prev,
            ...res.data,
          }));
          if (res.data.nickname !== undefined) {
            setNickname(res.data.nickname || '');
          }
          setTempRoles(prev => ({
            ...prev,
            is_bot: !!res.data.is_bot,
            is_moderator: !!res.data.is_moderator,
            is_vip: !!res.data.is_vip,
            is_subscriber: !!res.data.is_subscriber,
          }));
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          console.error('Error cargando detalles de usuario:', e);
        }
      }
    }
    loadUserDetails();
    return () => controller.abort();
  }, [username]);

  // Animación de entrada, inert isolation, focus trap, tecla Esc y botón atrás
  const isOpenUser = Boolean(user);
  useEffect(() => {
    if (!isOpenUser) return;
    isClosingRef.current = false;
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }

    triggerRef.current = document.activeElement;
    restoreInertRef.current = setupInertIsolation(drawerRef.current);

    const id = requestAnimationFrame(() => {
      setOpen(true);
      if (drawerRef.current) {
        const closeBtn = drawerRef.current.querySelector('.history-header-close');
        if (closeBtn) {
          closeBtn.focus();
        } else {
          const first = getFocusableElements(drawerRef.current)[0];
          if (first) first.focus();
        }
      }
    });

    window.history.pushState({ botDrawer: 'user-profile' }, '');

    function handleKeyDown(e) {
      if (confirmBanOpenRef.current || confirmUnbanOpenRef.current || confirmPurgeOpenRef.current) {
        return;
      }

      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        handleClose();
        return;
      }

      if (e.key === 'Tab') {
        trapFocus(drawerRef.current, e);
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('popstate', handlePopState);
    return () => {
      cancelAnimationFrame(id);
      if (closeTimerRef.current) {
        clearTimeout(closeTimerRef.current);
        closeTimerRef.current = null;
      }
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('popstate', handlePopState);
      if (restoreInertRef.current) {
        restoreInertRef.current();
        restoreInertRef.current = null;
      }
      const prevEl = triggerRef.current;
      if (prevEl && typeof prevEl.focus === 'function' && document.body.contains(prevEl)) {
        prevEl.focus();
      }
    };
  }, [isOpenUser]);

  useEffect(() => {
    hasSyncedRoles.current = false;
    setNickError(null);
    setRolesError(null);
    setModError(null);
  }, [username]);

  // Sincronizar roles desde Twitch una única vez al entrar a la pestaña 'roles'
  useEffect(() => {
    if (!username || activeTab !== 'roles' || hasSyncedRoles.current) return;
    let active = true;
    async function syncRoles() {
      setSyncingRoles(true);
      setRolesError(null);
      const res = await apiPost('/api/sync_user_roles', { username });
      if (!active) return;
      setSyncingRoles(false);
      hasSyncedRoles.current = true;
      if (res && res.ok && res.data) {
        setTempRoles({
          is_bot: !!res.data.is_bot,
          is_moderator: !!res.data.is_moderator,
          is_vip: !!res.data.is_vip,
          is_subscriber: !!res.data.is_subscriber,
        });
      } else {
        setRolesError((res && res.error) || 'No se pudieron sincronizar los roles.');
      }
    }
    syncRoles();
    return () => {
      active = false;
    };
  }, [username, activeTab]);

  // Debounce para búsqueda de mensajes
  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), 400);
    return () => clearTimeout(id);
  }, [searchInput]);

  const { messages, total, hasMore, loading, loadingMore, loadMore } = useMessageHistory(
    username,
    search,
    since,
    until
  );

  useEffect(() => {
    if (!loading && messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [loading]);

  useEffect(() => {
    if (!loadingMore && messagesRef.current) {
      const el = messagesRef.current;
      const delta = el.scrollHeight - prevScrollHeightRef.current;
      el.scrollTop = delta;
    }
  }, [loadingMore]);

  function handleScroll() {
    const el = messagesRef.current;
    if (!el || loadingMore || !hasMore) return;
    if (el.scrollTop < 80) {
      prevScrollHeightRef.current = el.scrollHeight;
      loadMore();
    }
  }

  async function handleSaveNickname() {
    setSavingNick(true);
    setNickError(null);
    const res = await apiPost('/api/set_nickname', {
      username,
      nickname: nickname.trim() || null,
    });
    setSavingNick(false);
    if (res && res.ok) {
      setEditingNick(false);
      setUserData(prev => ({ ...prev, nickname: res.data.nickname }));
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'success',
            data: { message: `Apodo de ${displayName} actualizado.` },
          },
        });
      }
    } else {
      const msg = (res && res.error) || 'No se pudo guardar el apodo.';
      setNickError(msg);
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'api_error',
            data: { message: msg },
          },
        });
      }
    }
  }

  async function handleSaveRoles() {
    setSavingRoles(true);
    setRolesError(null);
    const res = await apiPost('/api/update_user_roles', {
      username,
      is_bot: tempRoles.is_bot,
      is_moderator: tempRoles.is_moderator,
      is_vip: tempRoles.is_vip,
    });
    setSavingRoles(false);
    if (res && res.ok) {
      setUserData(prev => ({
        ...prev,
        is_bot: tempRoles.is_bot,
        is_moderator: tempRoles.is_moderator,
        is_vip: tempRoles.is_vip,
      }));
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'success',
            data: { message: `Roles de ${displayName} actualizados.` },
          },
        });
      }
    } else {
      const msg = (res && res.error) || 'No se pudieron guardar los roles.';
      setRolesError(msg);
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'api_error',
            data: { message: msg },
          },
        });
      }
    }
  }

  async function handleExecuteBan(reason) {
    setActionInProgress(true);
    setModError(null);
    const res = await apiPost('/api/moderation/ban', {
      username,
      reason: reason || undefined,
    });
    setActionInProgress(false);
    setConfirmBanOpen(false);

    if (res && res.ok) {
      setUserData(prev => ({
        ...prev,
        is_banned: true,
        ban_permanent: true,
        ban_reason: reason || null,
        ban_expires_at: null,
      }));
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'mod_action',
            data: { message: `Usuario ${displayName} baneado de Twitch.` },
          },
        });
      }
    } else {
      const msg = (res && res.error) || 'No se pudo banear al usuario.';
      setModError(msg);
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'api_error',
            data: { message: msg },
          },
        });
      }
    }
  }

  async function handleExecuteUnban() {
    setActionInProgress(true);
    setModError(null);
    const res = await apiPost('/api/moderation/unban', { username });
    setActionInProgress(false);
    setConfirmUnbanOpen(false);

    if (res && res.ok) {
      setUserData(prev => ({
        ...prev,
        is_banned: false,
        ban_permanent: false,
        ban_expires_at: null,
        ban_reason: null,
      }));
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'mod_action',
            data: { message: `Usuario ${displayName} desbaneado en Twitch.` },
          },
        });
      }
    } else {
      const msg = (res && res.error) || 'No se pudo desbanear al usuario.';
      setModError(msg);
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'api_error',
            data: { message: msg },
          },
        });
      }
    }
  }

  async function handleExecutePurge() {
    setActionInProgress(true);
    setModError(null);
    const res = await apiPost('/api/moderation/purge', { username });
    setActionInProgress(false);
    setConfirmPurgeOpen(false);

    if (res && res.ok) {
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'mod_action',
            data: { message: `Mensajes de ${displayName} purgados en Twitch.` },
          },
        });
      }
    } else {
      const msg = (res && res.error) || 'No se pudo purgar los mensajes.';
      setModError(msg);
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'api_error',
            data: { message: msg },
          },
        });
      }
    }
  }

  if (!user) return null;

  return html`
    <div class="history-backdrop" onClick=${handleClose} />

    <div
      class="history-drawer ${open ? 'open' : ''}"
      ref=${drawerRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="user-profile-drawer-title"
    >
      <!-- Cabecera de Perfil -->
      <div class="history-header">
        <div class="history-header-info">
          <div style="display:flex; align-items:center; gap:8px; min-width:0;">
            <span class="history-header-name" id="user-profile-drawer-title">${displayName}</span>
            <a
              href="https://twitch.tv/${encodeURIComponent(username)}"
              target="_blank"
              rel="noopener noreferrer"
              class="history-twitch-link"
              title="Abrir canal en Twitch"
            >
              <i class="fa-brands fa-twitch"></i>
              <span>Twitch</span>
              <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:11px;"></i>
            </a>
          </div>
          <div class="history-header-meta">
            ${
              user.display_name && user.display_name.toLowerCase() !== username.toLowerCase()
                ? html`<span class="history-header-username">@${username}</span>`
                : null
            }
            ${
              tempRoles.is_moderator
                ? html`<span
                    class="irc-badge badge-moderator"
                    style="font-size:11px;padding:1px 5px"
                    >Mod</span
                  >`
                : null
            }
            ${
              tempRoles.is_vip
                ? html`<span class="irc-badge badge-vip" style="font-size:11px;padding:1px 5px"
                    >VIP</span
                  >`
                : null
            }
            ${
              tempRoles.is_subscriber
                ? html`<span
                    class="irc-badge badge-subscriber"
                    style="font-size:11px;padding:1px 5px"
                    >Sub</span
                  >`
                : null
            }
            ${
              tempRoles.is_bot
                ? html`<span class="irc-badge badge-bot" style="font-size:11px;padding:1px 5px"
                    >Bot</span
                  >`
                : null
            }
            ${
              userData.is_banned
                ? html`<span class="irc-badge badge-banned" style="font-size:11px;padding:1px 5px"
                    >Baneado</span
                  >`
                : null
            }
          </div>
        </div>
        <button
          class="history-header-close"
          onClick=${handleClose}
          title="Cerrar perfil"
          aria-label="Cerrar perfil"
        >
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <!-- Navegación por Pestañas Internas del Drawer -->
      <div class="history-drawer-tabs" role="tablist" aria-label="Secciones del perfil">
        <button
          id="drawer-tab-info"
          role="tab"
          aria-selected=${activeTab === 'info'}
          aria-controls="drawer-panel-info"
          tabindex=${activeTab === 'info' ? 0 : -1}
          class="history-drawer-tab-btn ${activeTab === 'info' ? 'active' : ''}"
          onClick=${() => setActiveTab('info')}
          onKeyDown=${e => handleTabKeyDown(e, 'info')}
        >
          <i class="fa-solid fa-user-gear"></i> Detalle y Apodo
        </button>
        <button
          id="drawer-tab-roles"
          role="tab"
          aria-selected=${activeTab === 'roles'}
          aria-controls="drawer-panel-roles"
          tabindex=${activeTab === 'roles' ? 0 : -1}
          class="history-drawer-tab-btn ${activeTab === 'roles' ? 'active' : ''}"
          onClick=${() => setActiveTab('roles')}
          onKeyDown=${e => handleTabKeyDown(e, 'roles')}
        >
          <i class="fa-solid fa-shield-halved"></i> Roles y Moderación
        </button>
        <button
          id="drawer-tab-history"
          role="tab"
          aria-selected=${activeTab === 'history'}
          aria-controls="drawer-panel-history"
          tabindex=${activeTab === 'history' ? 0 : -1}
          class="history-drawer-tab-btn ${activeTab === 'history' ? 'active' : ''}"
          onClick=${() => setActiveTab('history')}
          onKeyDown=${e => handleTabKeyDown(e, 'history')}
        >
          <i class="fa-solid fa-comments"></i> Historial (${formatCount(total)})
        </button>
      </div>

      ${
        activeTab === 'info'
          ? html`
              <${UserInfoTabPanel}
                editingNick=${editingNick}
                setEditingNick=${val => {
                  setNickError(null);
                  setEditingNick(val);
                }}
                nickname=${nickname}
                setNickname=${setNickname}
                savingNick=${savingNick}
                nickError=${nickError}
                onSaveNickname=${handleSaveNickname}
                userData=${userData}
                total=${total}
              />
            `
          : null
      }
      ${
        activeTab === 'roles'
          ? html`
              <${UserRolesTabPanel}
                syncingRoles=${syncingRoles}
                savingRoles=${savingRoles}
                rolesError=${rolesError}
                modError=${modError}
                tempRoles=${tempRoles}
                setTempRoles=${setTempRoles}
                onSaveRoles=${handleSaveRoles}
                userData=${userData}
                actionInProgress=${actionInProgress}
                onOpenPurge=${() => setConfirmPurgeOpen(true)}
                onOpenUnban=${() => setConfirmUnbanOpen(true)}
                onOpenBan=${() => setConfirmBanOpen(true)}
              />
            `
          : null
      }
      ${
        activeTab === 'history'
          ? html`
              <${UserHistoryTabPanel}
                searchInput=${searchInput}
                setSearchInput=${setSearchInput}
                since=${since}
                setSince=${setSince}
                until=${until}
                setUntil=${setUntil}
                messagesRef=${messagesRef}
                onScroll=${handleScroll}
                loadingMore=${loadingMore}
                hasMore=${hasMore}
                messages=${messages}
                loading=${loading}
              />
            `
          : null
      }
    </div>

    <!-- Modal Confirmación Ban (pide la razón en el mismo modal) -->
    <${ConfirmModal}
      isOpen=${confirmBanOpen}
      title="¿Banear a ${displayName}?"
      message="El usuario perderá el acceso al chat del canal de Twitch."
      confirmText="Confirmar baneo"
      isDanger=${true}
      hasInput=${true}
      inputPlaceholder="Razón del baneo (opcional)"
      onConfirm=${handleExecuteBan}
      onClose=${() => setConfirmBanOpen(false)}
    />

    <!-- Modal Confirmación Purga -->
    <${ConfirmModal}
      isOpen=${confirmPurgeOpen}
      title="¿Purgar a ${displayName}?"
      message="Se limpiarán sus mensajes recientes en el chat de Twitch."
      confirmText="Confirmar purga"
      isDanger=${false}
      onConfirm=${handleExecutePurge}
      onClose=${() => setConfirmPurgeOpen(false)}
    />

    <!-- Modal Confirmación Desbaneo -->
    <${ConfirmModal}
      isOpen=${confirmUnbanOpen}
      title="¿Desbanear a ${displayName}?"
      message="El usuario recuperará el acceso para enviar mensajes en el chat de Twitch."
      confirmText="Confirmar desbaneo"
      isDanger=${false}
      onConfirm=${handleExecuteUnban}
      onClose=${() => setConfirmUnbanOpen(false)}
    />
  `;
}
