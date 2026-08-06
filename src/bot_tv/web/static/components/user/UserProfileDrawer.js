import { html, useState, useEffect, useRef } from 'preact-setup';
import { apiPost } from '/static/components/api.js';
import { ConfirmModal } from '/static/components/ConfirmModal.js';
import {
  useMessageHistory,
  formatCount,
  formatTimestamp,
} from '/static/components/followers/UserHistoryDrawer.js';
import { formatDate } from '/static/components/followers/followersUtils.js';

export function UserProfileDrawer({ user, onClose, dispatch }) {
  if (!user) return null;

  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('info'); // 'info', 'roles', 'history'

  // Datos del usuario local & roles
  const [userData, setUserData] = useState(user);
  const [nickname, setNickname] = useState(user.nickname || '');
  const [editingNick, setEditingNick] = useState(false);
  const [savingNick, setSavingNick] = useState(false);

  const [tempRoles, setTempRoles] = useState({
    is_bot: !!user.is_bot,
    is_moderator: !!user.is_moderator,
    is_vip: !!user.is_vip,
    is_subscriber: !!user.is_subscriber,
  });
  const [syncingRoles, setSyncingRoles] = useState(false);
  const [savingRoles, setSavingRoles] = useState(false);

  // Modales de Confirmación de Moderación
  const [confirmBanOpen, setConfirmBanOpen] = useState(false);
  const [confirmPurgeOpen, setConfirmPurgeOpen] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);

  // Filtros de historial de mensajes
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');
  const messagesRef = useRef(null);
  const prevScrollHeightRef = useRef(0);

  const username = user.username || user.display_name;
  const displayName = userData.display_name || user.display_name || username;

  // Animación de entrada y tecla Esc
  useEffect(() => {
    const id = requestAnimationFrame(() => setOpen(true));
    function handleKeyDown(e) {
      if (e.key === 'Escape') handleClose();
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      cancelAnimationFrame(id);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  // Sincronizar roles desde Twitch únicamente al entrar a la pestaña 'roles'
  useEffect(() => {
    if (activeTab !== 'roles') return;
    async function syncRoles() {
      setSyncingRoles(true);
      const res = await apiPost('/api/sync_user_roles', { username });
      setSyncingRoles(false);
      if (res && res.ok && res.data) {
        setTempRoles({
          is_bot: !!res.data.is_bot,
          is_moderator: !!res.data.is_moderator,
          is_vip: !!res.data.is_vip,
          is_subscriber: !!res.data.is_subscriber,
        });
      }
    }
    syncRoles();
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

  function handleClose() {
    setOpen(false);
    setTimeout(onClose, 300);
  }

  // Guardar Apodo
  async function handleSaveNickname() {
    setSavingNick(true);
    const res = await apiPost('/api/set_nickname', {
      username,
      nickname: nickname.trim() || null,
    });
    setSavingNick(false);
    setEditingNick(false);
    if (res && res.ok) {
      setUserData(prev => ({ ...prev, nickname: res.data.nickname }));
    }
  }

  // Guardar Roles
  async function handleSaveRoles() {
    setSavingRoles(true);
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
    }
  }

  // Ejecutar Ban con Razón opcional ingresada en ConfirmModal
  async function handleExecuteBan(reason) {
    setActionInProgress(true);
    const res = await apiPost('/api/moderation/ban', {
      username,
      reason: reason || undefined,
    });
    setActionInProgress(false);
    setConfirmBanOpen(false);

    if (res && res.ok) {
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
    } else if (dispatch) {
      dispatch({
        type: 'ADD_TOAST',
        toast: {
          id: Date.now().toString(),
          type: 'api_error',
          data: { message: res.error || 'No se pudo banear al usuario.' },
        },
      });
    }
  }

  // Ejecutar Purga (1s timeout)
  async function handleExecutePurge() {
    setActionInProgress(true);
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
    } else if (dispatch) {
      dispatch({
        type: 'ADD_TOAST',
        toast: {
          id: Date.now().toString(),
          type: 'api_error',
          data: { message: res.error || 'No se pudo purgar los mensajes.' },
        },
      });
    }
  }

  return html`
    <div class="history-backdrop" onClick=${handleClose} />

    <div class="history-drawer ${open ? 'open' : ''}">
      <!-- Cabecera de Perfil -->
      <div class="history-header">
        <div class="history-header-info">
          <span class="history-header-name">${displayName}</span>
          <div class="history-header-meta">
            ${
              user.display_name && user.display_name.toLowerCase() !== username.toLowerCase()
                ? html`<span class="history-header-username">@${username}</span>`
                : null
            }
            ${
              tempRoles.is_moderator
                ? html`<span class="irc-badge badge-moderator" style="font-size:9px;padding:1px 5px"
                    >Mod</span
                  >`
                : null
            }
            ${
              tempRoles.is_vip
                ? html`<span class="irc-badge badge-vip" style="font-size:9px;padding:1px 5px"
                    >VIP</span
                  >`
                : null
            }
            ${
              tempRoles.is_subscriber
                ? html`<span
                    class="irc-badge badge-subscriber"
                    style="font-size:9px;padding:1px 5px"
                    >Sub</span
                  >`
                : null
            }
            ${
              tempRoles.is_bot
                ? html`<span class="irc-badge badge-bot" style="font-size:9px;padding:1px 5px"
                    >Bot</span
                  >`
                : null
            }
          </div>
        </div>
        <button class="history-header-close" onClick=${handleClose} title="Cerrar perfil">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <!-- Navegación por Pestañas Internas del Drawer -->
      <div style="display:flex; border-bottom:var(--border-2); background:var(--surface);">
        <button
          class="btn"
          style="flex:1; border-radius:0; border:none; background:${activeTab === 'info' ? 'var(--surface2)' : 'none'}; color:${activeTab === 'info' ? 'var(--accent-text)' : 'var(--text-muted)'}; font-size:12.5px; padding:10px;"
          onClick=${() => setActiveTab('info')}
        >
          <i class="fa-solid fa-user-gear" style="margin-right:6px;"></i> Detalle y Apodo
        </button>
        <button
          class="btn"
          style="flex:1; border-radius:0; border:none; background:${activeTab === 'roles' ? 'var(--surface2)' : 'none'}; color:${activeTab === 'roles' ? 'var(--accent-text)' : 'var(--text-muted)'}; font-size:12.5px; padding:10px;"
          onClick=${() => setActiveTab('roles')}
        >
          <i class="fa-solid fa-shield-halved" style="margin-right:6px;"></i> Roles y Moderación
        </button>
        <button
          class="btn"
          style="flex:1; border-radius:0; border:none; background:${activeTab === 'history' ? 'var(--surface2)' : 'none'}; color:${activeTab === 'history' ? 'var(--accent-text)' : 'var(--text-muted)'}; font-size:12.5px; padding:10px;"
          onClick=${() => setActiveTab('history')}
        >
          <i class="fa-solid fa-comments" style="margin-right:6px;"></i> Historial
          (${formatCount(total)})
        </button>
      </div>

      <!-- Contenido Tab 1: Detalle y Apodo -->
      ${
        activeTab === 'info'
          ? html`
              <div
                style="padding:16px; display:flex; flex-direction:column; gap:16px; overflow-y:auto; flex:1;"
              >
                <!-- Apodo Local -->
                <div
                  style="background:var(--surface2); border:1px solid var(--border-2); border-radius:var(--radius-sm); padding:14px;"
                >
                  <div
                    style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;"
                  >
                    <span
                      style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted);"
                      >Apodo en la app</span
                    >
                    ${
                      !editingNick
                        ? html`
                            <button
                              class="btn"
                              style="font-size:11px; padding:3px 8px; background:var(--surface3);"
                              onClick=${() => setEditingNick(true)}
                            >
                              <i class="fa-solid fa-pen-to-square"></i> Editar
                            </button>
                          `
                        : null
                    }
                  </div>

                  ${
                    editingNick
                      ? html`
                          <div style="display:flex; gap:8px;">
                            <input
                              type="text"
                              style="flex:1; background:var(--surface); border:var(--border); border-radius:var(--radius-xs); color:var(--text); padding:6px 10px; font-size:13px; outline:none;"
                              value=${nickname}
                              onInput=${e => setNickname(e.target.value)}
                              placeholder="Sin apodo"
                              disabled=${savingNick}
                            />
                            <button
                              class="btn btn-primary"
                              style="padding:6px 12px; font-size:12px;"
                              onClick=${handleSaveNickname}
                              disabled=${savingNick}
                            >
                              ${savingNick ? html`<i class="fa-solid fa-spinner fa-spin"></i>` : 'Guardar'}
                            </button>
                            <button
                              class="btn btn-secondary"
                              style="padding:6px 12px; font-size:12px;"
                              onClick=${() => setEditingNick(false)}
                              disabled=${savingNick}
                            >
                              Cancelar
                            </button>
                          </div>
                        `
                      : html`
                          <div style="font-size:14px; color:var(--text-2);">
                            ${userData.nickname ? html`<strong>${userData.nickname}</strong>` : html`<em style="color:var(--text-muted);">Sin apodo asignado</em>`}
                          </div>
                        `
                  }
                </div>

                <!-- Datos de Seguimiento -->
                <div
                  style="background:var(--surface2); border:1px solid var(--border-2); border-radius:var(--radius-sm); padding:14px; display:flex; flex-direction:column; gap:10px;"
                >
                  <span
                    style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted);"
                    >Estado en el Canal</span
                  >

                  <div style="font-size:13px;">
                    ${
                      userData.is_broadcaster
                        ? html`<span class="irc-badge badge-broadcaster">Broadcaster</span>`
                        : userData.is_follower
                          ? html`
                              <span class="irc-badge badge-follower" style="margin-right:6px;"
                                >Seguidor</span
                              >
                              <span style="color:var(--text-muted);"
                                >desde ${formatDate(userData.followed_at)}</span
                              >
                            `
                          : userData.unfollowed_at
                            ? html`
                                <span class="irc-badge badge-unfollower" style="margin-right:6px;"
                                  >Dejó de seguir</span
                                >
                                <span style="color:var(--text-muted);"
                                  >(${formatDate(userData.unfollowed_at)})</span
                                >
                              `
                            : html`<span class="irc-badge badge-never-follower"
                                >Nunca ha seguido</span
                              >`
                    }
                  </div>

                  <div
                    style="font-size:12px; color:var(--text-muted); display:flex; justify-content:space-between; margin-top:4px;"
                  >
                    <span>Total mensajes registrados:</span>
                    <strong style="color:var(--accent-text);">${formatCount(total)}</strong>
                  </div>
                </div>
              </div>
            `
          : null
      }

      <!-- Contenido Tab 2: Roles y Moderación -->
      ${
        activeTab === 'roles'
          ? html`
              <div
                style="padding:16px; display:flex; flex-direction:column; gap:20px; overflow-y:auto; flex:1;"
              >
                <!-- Asignación de Roles -->
                <div
                  style="background:var(--surface2); border:1px solid var(--border-2); border-radius:var(--radius-sm); padding:14px;"
                >
                  <div
                    style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;"
                  >
                    <span
                      style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted);"
                      >Gestión de Roles</span
                    >
                    ${syncingRoles ? html`<span style="font-size:11px; color:var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Sincronizando...</span>` : null}
                  </div>

                  <div style="display:flex; flex-direction:column; gap:10px;">
                    <label
                      style="display:flex; justify-content:space-between; align-items:center; cursor:pointer;"
                    >
                      <span style="font-size:13px; color:var(--text);">Moderador</span>
                      <input
                        type="checkbox"
                        class="role-toggle-checkbox"
                        checked=${tempRoles.is_moderator}
                        onChange=${e => setTempRoles({ ...tempRoles, is_moderator: e.target.checked })}
                      />
                    </label>

                    <label
                      style="display:flex; justify-content:space-between; align-items:center; cursor:pointer;"
                    >
                      <span style="font-size:13px; color:var(--text);">VIP</span>
                      <input
                        type="checkbox"
                        class="role-toggle-checkbox"
                        checked=${tempRoles.is_vip}
                        onChange=${e => setTempRoles({ ...tempRoles, is_vip: e.target.checked })}
                      />
                    </label>

                    <label
                      style="display:flex; justify-content:space-between; align-items:center; cursor:pointer;"
                    >
                      <span style="font-size:13px; color:var(--text);">Bot de Chat</span>
                      <input
                        type="checkbox"
                        class="role-toggle-checkbox"
                        checked=${tempRoles.is_bot}
                        onChange=${e => setTempRoles({ ...tempRoles, is_bot: e.target.checked })}
                      />
                    </label>
                  </div>

                  <button
                    class="btn btn-primary"
                    style="width:100%; margin-top:14px; padding:8px;"
                    onClick=${handleSaveRoles}
                    disabled=${savingRoles}
                  >
                    ${savingRoles ? html`<i class="fa-solid fa-spinner fa-spin"></i> Guardando...` : 'Guardar Roles'}
                  </button>
                </div>

                <!-- Acciones de Moderación Directa -->
                <div
                  style="background:rgba(248, 113, 113, 0.05); border:1px solid rgba(248, 113, 113, 0.2); border-radius:var(--radius-sm); padding:14px; display:flex; flex-direction:column; gap:12px;"
                >
                  <span
                    style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--danger);"
                    >Acciones de Moderación</span
                  >

                  <div style="display:flex; gap:10px;">
                    <button
                      class="btn"
                      style="flex:1; background:rgba(255,255,255,0.05); border:var(--border-2); color:var(--text-2); font-size:12px; padding:10px;"
                      onClick=${() => setConfirmPurgeOpen(true)}
                      disabled=${actionInProgress}
                    >
                      <i
                        class="fa-solid fa-broom"
                        style="margin-right:6px; color:var(--warning);"
                      ></i>
                      Purgar mensajes
                    </button>
                    <button
                      class="btn btn-danger"
                      style="flex:1; font-size:12px; padding:10px;"
                      onClick=${() => setConfirmBanOpen(true)}
                      disabled=${actionInProgress}
                    >
                      <i class="fa-solid fa-ban" style="margin-right:6px;"></i> Banear usuario
                    </button>
                  </div>
                </div>
              </div>
            `
          : null
      }

      <!-- Contenido Tab 3: Historial de Mensajes -->
      ${
        activeTab === 'history'
          ? html`
              <!-- Buscador y fechas -->
              <div class="history-search">
                <div class="history-search-input-wrap">
                  <i class="fa-solid fa-magnifying-glass history-search-icon"></i>
                  <input
                    type="text"
                    class="history-search-input"
                    placeholder="Buscar en mensajes..."
                    value=${searchInput}
                    onInput=${e => setSearchInput(e.target.value)}
                  />
                </div>
                <div class="history-search-dates">
                  <input
                    type="date"
                    value=${since}
                    onChange=${e => setSince(e.target.value)}
                    max=${until || ''}
                    title="Desde"
                  />
                  <span class="history-search-sep">—</span>
                  <input
                    type="date"
                    value=${until}
                    onChange=${e => setUntil(e.target.value)}
                    min=${since || ''}
                    title="Hasta"
                  />
                  ${
                    searchInput || since || until
                      ? html`
                          <button
                            class="history-search-clear"
                            onClick=${() => {
                              setSearchInput('');
                              setSince('');
                              setUntil('');
                            }}
                          >
                            <i class="fa-solid fa-xmark"></i> Limpiar
                          </button>
                        `
                      : null
                  }
                </div>
              </div>

              <!-- Lista de mensajes -->
              <div class="history-messages" ref=${messagesRef} onScroll=${handleScroll}>
                ${
                  loadingMore
                    ? html`<div class="history-load-more">
                        <span class="history-spinner"></span> Cargando anteriores...
                      </div>`
                    : hasMore
                      ? html`<div
                          class="history-load-more"
                          style="color:var(--text-muted);font-size:11px;"
                        >
                          Sube para cargar más
                        </div>`
                      : messages.length > 0
                        ? html`<div
                            class="history-load-more"
                            style="color:var(--text-muted);font-size:11px;"
                          >
                            Inicio del historial
                          </div>`
                        : null
                }
                ${
                  loading
                    ? html`<div class="history-empty">
                        <span
                          class="history-spinner"
                          style="width:20px;height:20px;border-width:3px;"
                        ></span>
                        <p>Cargando mensajes...</p>
                      </div>`
                    : messages.length === 0
                      ? html`<div class="history-empty">
                          <i class="fa-solid fa-comment-slash"></i>
                          <p>No hay mensajes registrados.</p>
                        </div>`
                      : html`
                          <div class="history-msg-list">
                            ${messages.map(
                              m => html`
                                <div class="history-msg" key=${m.id || m.timestamp}>
                                  <span class="history-msg-time"
                                    >${formatTimestamp(m.timestamp)}</span
                                  >
                                  <span class="history-msg-text">${m.message || m.text}</span>
                                </div>
                              `
                            )}
                          </div>
                        `
                }
              </div>
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
  `;
}
