import { html, useState, useEffect, useRef } from 'preact-setup';
import { apiPost, apiGet } from '/static/components/api.js';
import { CustomSelect } from '/static/components/CustomSelect.js';
import { UserHistoryDrawer } from '/static/components/followers/UserHistoryDrawer.js';

function formatDate(isoString) {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString('es-ES', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

function getPageNumbers(current, total) {
  const pages = [];
  const maxVisible = 5;

  if (total <= maxVisible) {
    for (let i = 1; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);

    let start = Math.max(2, current - 1);
    let end = Math.min(total - 1, current + 1);

    if (current <= 3) {
      end = 4;
    } else if (current >= total - 2) {
      start = total - 3;
    }

    if (start > 2) {
      pages.push('...');
    }

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (end < total - 1) {
      pages.push('...');
    }

    pages.push(total);
  }
  return pages;
}

function getTodayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const SELECT_OPTIONS = [
  { value: 'all', label: 'Todos los usuarios' },
  { value: 'follower', label: 'Seguidor' },
  { value: 'not_follower', label: 'No Seguidor' },
  { value: 'unfollower', label: 'Dejó de Seguir' },
];

const ROLE_OPTIONS = [
  { value: 'all', label: 'Todos los roles' },
  { value: 'moderator', label: 'Moderador' },
  { value: 'vip', label: 'VIP' },
  { value: 'subscriber', label: 'Suscriptor' },
  { value: 'bot', label: 'Bot' },
];

export function FollowersTab({ followers }) {
  const allNewLabels = followers.allNewLabels || [];
  const allLostLabels = followers.allLostLabels || [];
  const [syncing, setSyncing] = useState(false);
  const [result, setResult] = useState(null);

  // Estados para filtros de listado de usuarios
  const [nameInput, setNameInput] = useState('');
  const [nameSearch, setNameSearch] = useState('');
  const [isFollower, setIsFollower] = useState('all'); // 'all', 'true', 'false'
  const [role, setRole] = useState('all');
  const [followedAfter, setFollowedAfter] = useState('');
  const [followedBefore, setFollowedBefore] = useState('');
  const [unfollowedAfter, setUnfollowedAfter] = useState('');
  const [unfollowedBefore, setUnfollowedBefore] = useState('');

  // Estados de ordenamiento
  const [sortBy, setSortBy] = useState('username'); // 'username', 'role', 'follow_date'
  const [sortOrder, setSortOrder] = useState('asc'); // 'asc', 'desc'

  // Estados de paginación y carga
  const [users, setUsers] = useState([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [page, setPage] = useState(1);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(null); // trackea acciones rápidas por usuario
  const [selectedUserForRoles, setSelectedUserForRoles] = useState(null);
  const [historyUser, setHistoryUser] = useState(null);
  const [tempRoles, setTempRoles] = useState({
    is_bot: false,
    is_moderator: false,
    is_vip: false,
    is_subscriber: false,
  });

  const limit = 50;
  const sync = followers.lastSync;
  const prog = followers.progress;

  // Ref para almacenar filtros anteriores y prevenir doble fetch
  const prevFilters = useRef({
    nameSearch,
    isFollower,
    role,
    followedAfter,
    followedBefore,
    unfollowedAfter,
    unfollowedBefore,
    sortBy,
    sortOrder,
  });

  // Debounce del buscador de nombre (1s)
  useEffect(() => {
    const timer = setTimeout(() => {
      setNameSearch(nameInput);
    }, 1000);
    return () => clearTimeout(timer);
  }, [nameInput]);

  // Efecto que controla la carga al cambiar filtros o paginar
  useEffect(() => {
    const filtersChanged =
      prevFilters.current.nameSearch !== nameSearch ||
      prevFilters.current.isFollower !== isFollower ||
      prevFilters.current.role !== role ||
      prevFilters.current.followedAfter !== followedAfter ||
      prevFilters.current.followedBefore !== followedBefore ||
      prevFilters.current.unfollowedAfter !== unfollowedAfter ||
      prevFilters.current.unfollowedBefore !== unfollowedBefore ||
      prevFilters.current.sortBy !== sortBy ||
      prevFilters.current.sortOrder !== sortOrder;

    prevFilters.current = {
      nameSearch,
      isFollower,
      role,
      followedAfter,
      followedBefore,
      unfollowedAfter,
      unfollowedBefore,
      sortBy,
      sortOrder,
    };

    if (filtersChanged && page !== 1) {
      setPage(1); // Esto disparará nuevamente el useEffect al cambiar la página
    } else {
      fetchUsers();
    }
  }, [
    page,
    nameSearch,
    isFollower,
    role,
    followedAfter,
    followedBefore,
    unfollowedAfter,
    unfollowedBefore,
    sortBy,
    sortOrder,
  ]);

  // Efecto para limpiar campos de fecha del filtro opuesto si cambia el combo de estado
  useEffect(() => {
    if (isFollower === 'follower') {
      setUnfollowedAfter('');
      setUnfollowedBefore('');
    } else if (isFollower === 'unfollower') {
      setFollowedAfter('');
      setFollowedBefore('');
    } else if (isFollower === 'not_follower') {
      setFollowedAfter('');
      setFollowedBefore('');
      setUnfollowedAfter('');
      setUnfollowedBefore('');
    }
  }, [isFollower]);

  async function fetchUsers() {
    setLoadingUsers(true);
    const params = new window.URLSearchParams();
    if (nameSearch.trim()) params.append('name', nameSearch.trim());
    if (isFollower !== 'all') params.append('is_follower', isFollower);
    if (role !== 'all') params.append('role', role);
    if (followedAfter) params.append('followed_after', followedAfter);
    if (followedBefore) params.append('followed_before', followedBefore);
    if (unfollowedAfter) params.append('unfollowed_after', unfollowedAfter);
    if (unfollowedBefore) params.append('unfollowed_before', unfollowedBefore);
    if (sortBy) params.append('sort_by', sortBy);
    if (sortOrder) params.append('sort_order', sortOrder);
    params.append('limit', limit.toString());
    params.append('page', page.toString());

    const res = await apiGet(`/api/users?${params.toString()}`);
    setLoadingUsers(false);
    if (res && res.ok && res.data) {
      setUsers(res.data.users || []);
      setTotalUsers(res.data.total || 0);
    } else {
      setUsers([]);
      setTotalUsers(0);
    }
  }

  function handleSort(field) {
    if (sortBy === field) {
      setSortOrder(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  }

  async function handleSync() {
    setSyncing(true);
    setResult(null);
    const data = await apiPost('/api/sync_followers', {});
    setSyncing(false);
    if (data.ok) {
      setResult({ ok: true, msg: 'Sincronización completada.' });
      fetchUsers(); // Actualizar listado tras sincronizar
      setTimeout(() => {
        setResult(null);
      }, 5000);
    } else {
      setResult({ ok: false, msg: data.error || 'Error al sincronizar.' });
    }
  }

  // Acciones rápidas sobre los usuarios de la tabla
  async function openRolesModal(u) {
    setActionInProgress(u.username);
    const res = await apiPost('/api/sync_user_roles', {
      username: u.username,
    });
    setActionInProgress(null);
    if (res && res.ok && res.data) {
      setSelectedUserForRoles(u);
      setTempRoles({
        is_bot: !!res.data.is_bot,
        is_moderator: !!res.data.is_moderator,
        is_vip: !!res.data.is_vip,
        is_subscriber: !!res.data.is_subscriber,
      });
      fetchUsers();
    } else {
      window.alert(
        res
          ? res.error || 'Error al sincronizar roles con Twitch.'
          : 'Error al sincronizar roles con Twitch.'
      );
    }
  }

  async function handleSaveRoles() {
    if (!selectedUserForRoles) return;
    setActionInProgress(selectedUserForRoles.username);
    const res = await apiPost('/api/update_user_roles', {
      username: selectedUserForRoles.username,
      is_bot: tempRoles.is_bot,
      is_moderator: tempRoles.is_moderator,
      is_vip: tempRoles.is_vip,
    });
    setActionInProgress(null);
    setSelectedUserForRoles(null);
    if (res && res.ok) {
      fetchUsers();
    } else {
      window.alert(res.error || 'Error al actualizar los roles.');
    }
  }

  async function handleSetNickname(u) {
    const msg = `Introduce el apodo para ${u.display_name || u.username} (deja en blanco para eliminarlo):`;
    const newNick = window.prompt(msg, u.nickname || '');
    if (newNick === null) return; // cancelado

    setActionInProgress(u.username);
    const res = await apiPost('/api/set_nickname', {
      username: u.username,
      nickname: newNick.trim() || null,
    });
    setActionInProgress(null);
    if (res && res.ok) {
      fetchUsers();
    }
  }

  function handleClearFilters() {
    setNameInput('');
    setNameSearch('');
    setIsFollower('all');
    setRole('all');
    setFollowedAfter('');
    setFollowedBefore('');
    setUnfollowedAfter('');
    setUnfollowedBefore('');
    setSortBy('username');
    setSortOrder('asc');
    setPage(1);
  }

  const progPct = prog && prog.total > 0 ? Math.round((prog.count / prog.total) * 100) : 0;
  const totalPages = Math.ceil(totalUsers / limit);

  return html`
    <div class="panel" id="followers-panel" style="display:flex; flex-direction:column; gap:24px;">
      <!-- Grid de Resumen y Sync (Dos columnas) -->
      <div
        class="two-col-grid"
        style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:20px;"
      >
        <!-- Columna Izquierda: Resumen y Sincronizador -->
        <div class="two-col">
          <div class="section">
            <div class="section-header">
              <span class="section-icon"><i class="fa-solid fa-chart-simple"></i></span> Resumen
            </div>
            <div class="section-body">
              <div class="followers-stat">
                <div class="stat-card">
                  <div class="stat-value">${sync?.total ?? '—'}</div>
                  <div class="stat-label">Total</div>
                </div>
                <div class="stat-card new">
                  <div class="stat-value">${allNewLabels.length || '—'}</div>
                  <div class="stat-label">Nuevos</div>
                </div>
                <div class="stat-card lost">
                  <div class="stat-value">${allLostLabels.length || '—'}</div>
                  <div class="stat-label">Perdidos</div>
                </div>
              </div>

              ${
                prog
                  ? html`
                      <div>
                        <div class="progress-text" style="margin-bottom:6px">
                          ${
                            prog.total > 0
                              ? `${prog.count} / ${prog.total} seguidores`
                              : 'Iniciando sincronización...'
                          }
                        </div>
                        <div class="progress-bar-wrap">
                          <div class="progress-bar-fill" style="width:${progPct}%"></div>
                        </div>
                      </div>
                    `
                  : null
              }

              <button
                id="btn-sync-followers"
                class="btn btn-primary"
                style="width:100%"
                onClick=${handleSync}
                disabled=${syncing || !!prog || !sync}
              >
                ${
                  syncing || !!prog
                    ? html`<span class="spinner"></span> Sincronizando...`
                    : !sync
                      ? html`<span class="spinner"></span> Inicializando bot...`
                      : html`<i class="fa-solid fa-rotate"></i> Sincronizar ahora`
                }
              </button>

              ${
                result
                  ? html`<div class="result-msg ${result.ok ? 'ok' : 'err'}">${result.msg}</div>`
                  : null
              }
            </div>
          </div>

          ${
            !sync
              ? html`
                  <div
                    style="text-align:center;color:var(--text-muted);font-size:13px;padding:20px"
                  >
                    Sin datos de sync. Presiona "Sincronizar ahora" o espera la sincronización
                    automática al iniciar.
                  </div>
                `
              : null
          }
        </div>

        <!-- Columna Derecha: Nuevos y Perdidos acumulados en la sesion -->
        ${
          allNewLabels.length > 0 || allLostLabels.length > 0
            ? html`
                <div class="two-col">
                  <!-- Nuevos seguidores -->
                  ${
                    allNewLabels.length > 0
                      ? html`
                          <div class="section">
                            <div class="section-header" style="color:var(--success)">
                              <span class="section-icon"
                                ><i class="fa-solid fa-user-plus"></i
                              ></span>
                              Nuevos (${allNewLabels.length})
                            </div>
                            <div class="section-body">
                              <div class="follower-list">
                                ${allNewLabels.map(
                                (l, i) => html`<div key=${i} class="follower-item new">${l}</div>`
                              )}
                              </div>
                            </div>
                          </div>
                        `
                      : null
                  }

                  <!-- Perdidos -->
                  ${
                    allLostLabels.length > 0
                      ? html`
                          <div class="section">
                            <div class="section-header" style="color:var(--danger)">
                              <span class="section-icon"
                                ><i class="fa-solid fa-user-minus"></i
                              ></span>
                              Dejaron de seguir (${allLostLabels.length})
                            </div>
                            <div class="section-body">
                              <div class="follower-list">
                                ${allLostLabels.map(
                                (l, i) => html`<div key=${i} class="follower-item lost">${l}</div>`
                              )}
                              </div>
                            </div>
                          </div>
                        `
                      : null
                  }
                </div>
              `
            : null
        }
      </div>

      <!-- Sección inferior: Listado de Usuarios con Filtros Avanzados -->
      <div class="section" style="border-top: 1px solid var(--border-2); padding-top: 24px;">
        <div
          class="section-header"
          style="display:flex; justify-content:space-between; align-items:center;"
        >
          <div>
            <span class="section-icon"><i class="fa-solid fa-users"></i></span> Buscador de Usuarios
            y Seguidores
          </div>
          ${
            !loadingUsers && totalUsers > 0
              ? html`
                  <span style="font-size: 12px; color: var(--text-muted); font-weight: normal;">
                    Total:
                    <strong style="color: var(--accent-text);">${totalUsers}</strong> usuarios
                    encontrados
                  </span>
                `
              : null
          }
        </div>

        <div class="section-body" style="gap:16px;">
          <!-- Barra de filtros -->
          <div class="filters-bar">
            <!-- Buscar por Nombre -->
            <div class="filter-group">
              <label class="filter-label">Nombre / Apodo</label>
              <input
                type="text"
                placeholder="Buscar usuario..."
                value=${nameInput}
                onInput=${e => setNameInput(e.target.value)}
              />
            </div>

            <!-- Estado de Seguidor -->
            <div class="filter-group">
              <label class="filter-label">Estado Seguimiento</label>
              <${CustomSelect}
                value=${isFollower}
                onChange=${setIsFollower}
                options=${SELECT_OPTIONS}
              />
            </div>

            <!-- Rol -->
            <div class="filter-group">
              <label class="filter-label">Rol</label>
              <${CustomSelect} value=${role} onChange=${setRole} options=${ROLE_OPTIONS} />
            </div>

            <!-- Rango Fecha Seguimiento -->
            <div class="filter-group">
              <label class="filter-label">Seguidor desde</label>
              <div class="filter-dates-row">
                <input
                  type="date"
                  value=${followedAfter}
                  onChange=${e => {
                    const val = e.target.value;
                    setFollowedAfter(val);
                    if (val) {
                      setIsFollower('follower');
                      if (!followedBefore) {
                        setFollowedBefore(getTodayStr());
                      }
                    }
                  }}
                  placeholder="Desde"
                  disabled=${isFollower === 'not_follower' || isFollower === 'unfollower'}
                  max=${followedBefore || ''}
                />
                <span class="filter-separator">a</span>
                <input
                  type="date"
                  value=${followedBefore}
                  onChange=${e => {
                    const val = e.target.value;
                    setFollowedBefore(val);
                    if (val) {
                      setIsFollower('follower');
                      if (!followedAfter) {
                        setFollowedAfter(val);
                      }
                    }
                  }}
                  placeholder="Hasta"
                  disabled=${isFollower === 'not_follower' || isFollower === 'unfollower'}
                  min=${followedAfter || ''}
                />
              </div>
            </div>

            <!-- Rango Fecha Unfollow -->
            <div class="filter-group">
              <label class="filter-label">Dejó de seguir</label>
              <div class="filter-dates-row">
                <input
                  type="date"
                  value=${unfollowedAfter}
                  onChange=${e => {
                    const val = e.target.value;
                    setUnfollowedAfter(val);
                    if (val) {
                      setIsFollower('unfollower');
                      if (!unfollowedBefore) {
                        setUnfollowedBefore(getTodayStr());
                      }
                    }
                  }}
                  placeholder="Desde"
                  disabled=${isFollower === 'follower' || isFollower === 'not_follower'}
                  max=${unfollowedBefore || ''}
                />
                <span class="filter-separator">a</span>
                <input
                  type="date"
                  value=${unfollowedBefore}
                  onChange=${e => {
                    const val = e.target.value;
                    setUnfollowedBefore(val);
                    if (val) {
                      setIsFollower('unfollower');
                      if (!unfollowedAfter) {
                        setUnfollowedAfter(val);
                      }
                    }
                  }}
                  placeholder="Hasta"
                  disabled=${isFollower === 'follower' || isFollower === 'not_follower'}
                  min=${unfollowedAfter || ''}
                />
              </div>
            </div>

            <!-- Botón Limpiar -->
            <div class="filter-group filter-group-actions">
              <button
                class="btn btn-secondary btn-icon"
                onClick=${handleClearFilters}
                title="Limpiar filtros"
              >
                <i class="fa-solid fa-filter-circle-xmark"></i> Limpiar
              </button>
            </div>
          </div>

          <!-- Tabla de Resultados -->
          <div>
            <div
              class="users-table-wrapper ${loadingUsers ? 'loading' : ''}"
              style="border-radius: var(--radius-sm) var(--radius-sm) 0 0; border-bottom: none; position: relative;"
            >
              ${
                loadingUsers &&
                html`
                  <div class="table-loading-overlay">
                    <span class="spinner"></span> Cargando usuarios...
                  </div>
                `
              }
              ${
                users.length === 0
                  ? html`<div class="empty-table" style="border-bottom: 1px solid var(--border-2);">
                      No se encontraron usuarios con los filtros seleccionados.
                    </div>`
                  : html`
                      <table class="users-table">
                        <thead>
                          <tr>
                            <th
                              class="sortable"
                              onClick=${() => handleSort('username')}
                              title="Ordenar por usuario (alfabético)"
                            >
                              Usuario
                              ${
                                sortBy === 'username'
                                  ? html`<i
                                      class="fa-solid fa-sort-${sortOrder === 'asc' ? 'up' : 'down'}"
                                    ></i>`
                                  : html`<i class="fa-solid fa-sort sort-icon-muted"></i>`
                              }
                            </th>
                            <th
                              class="sortable"
                              onClick=${() => handleSort('role')}
                              title="Ordenar por rol prioritario (Moderador -> VIP -> Suscriptor -> Bot)"
                            >
                              Roles
                              ${
                                sortBy === 'role'
                                  ? html`<i
                                      class="fa-solid fa-sort-${sortOrder === 'asc' ? 'up' : 'down'}"
                                    ></i>`
                                  : html`<i class="fa-solid fa-sort sort-icon-muted"></i>`
                              }
                            </th>
                            <th
                              class="sortable"
                              onClick=${() => handleSort('follow_date')}
                              title="Ordenar por fecha y hora de seguimiento / unfollow"
                            >
                              Estado Seguimiento
                              ${
                                sortBy === 'follow_date'
                                  ? html`<i
                                      class="fa-solid fa-sort-${sortOrder === 'asc' ? 'up' : 'down'}"
                                    ></i>`
                                  : html`<i class="fa-solid fa-sort sort-icon-muted"></i>`
                              }
                            </th>
                            <th style="width: 120px; text-align: center;">Acciones</th>
                          </tr>
                        </thead>
                        <tbody>
                          ${users.map(u => {
                            const isActioning = actionInProgress === u.username;
                            return html`
                              <tr key=${u.user_id || u.username}>
                                <!-- Info del Usuario -->
                                <td data-label="Usuario">
                                  <div class="user-info-cell">
                                    <div class="user-display-name">
                                      ${u.display_name || u.username}
                                    </div>
                                    ${
                                    u.nickname ||
                                    (u.display_name &&
                                      u.display_name.toLowerCase() !== u.username.toLowerCase())
                                      ? html`
                                          <div class="user-sub-names">
                                            ${
                                              u.nickname
                                                ? html`<span class="user-nickname-tag"
                                                    ><i class="fa-solid fa-signature"></i>
                                                    ${u.nickname}</span
                                                  >`
                                                : null
                                            }
                                            ${
                                              u.display_name &&
                                              u.display_name.toLowerCase() !==
                                                u.username.toLowerCase()
                                                ? html`<span>@${u.username}</span>`
                                                : null
                                            }
                                          </div>
                                        `
                                      : null
                                  }
                                    ${
                                    u.message_count > 0
                                      ? html`
                                          <div class="user-sub-names" style="margin-top:2px;">
                                            <span style="color:var(--text-muted);font-size:11px;">
                                              <i
                                                class="fa-solid fa-message"
                                                style="font-size:9px;margin-right:3px;"
                                              ></i>
                                              ${u.message_count.toLocaleString('es-ES')}
                                            </span>
                                          </div>
                                        `
                                      : null
                                  }
                                  </div>
                                </td>

                                <!-- Roles -->
                                <td data-label="Roles">
                                  <div class="irc-user-badges">
                                    ${
                                    u.is_moderator
                                      ? html`<span class="irc-badge badge-moderator">Mod</span>`
                                      : null
                                  }
                                    ${
                                    u.is_vip
                                      ? html`<span class="irc-badge badge-vip">VIP</span>`
                                      : null
                                  }
                                    ${
                                    u.is_subscriber
                                      ? html`<span class="irc-badge badge-subscriber"
                                          >${
                                            u.sub_tier === '3000'
                                              ? 'Sub T3'
                                              : u.sub_tier === '2000'
                                                ? 'Sub T2'
                                                : 'Sub T1'
                                          }</span
                                        >`
                                      : null
                                  }
                                    ${
                                    u.is_bot
                                      ? html`<span class="irc-badge badge-bot">Bot</span>`
                                      : null
                                  }
                                  </div>
                                </td>

                                <!-- Estado Seguimiento -->
                                <td data-label="Seguimiento">
                                  ${
                                  u.is_broadcaster
                                    ? html`<span class="irc-badge badge-broadcaster"
                                        >Broadcaster</span
                                      >`
                                    : u.is_follower
                                      ? html`
                                          <div class="follow-status-wrap">
                                            <span class="irc-badge badge-follower">Seguidor</span>
                                            <span class="follow-date-text"
                                              >desde ${formatDate(u.followed_at)}</span
                                            >
                                          </div>
                                        `
                                      : u.unfollowed_at
                                        ? html`
                                            <div class="follow-status-wrap">
                                              <span class="irc-badge badge-unfollower"
                                                >Dejó de seguir</span
                                              >
                                              <span class="follow-date-text"
                                                >Seguidor: ${formatDate(u.followed_at)}</span
                                              >
                                              <span class="follow-date-text"
                                                >Unfollow: ${formatDate(u.unfollowed_at)}</span
                                              >
                                            </div>
                                          `
                                        : html`<span class="irc-badge badge-never-follower"
                                            >Nunca ha seguido</span
                                          >`
                                }
                                </td>

                                <!-- Acciones rápidas -->
                                <td data-label="Acciones">
                                  <div class="user-table-actions">
                                    <button
                                      class="btn btn-secondary btn-sm"
                                      onClick=${() => openRolesModal(u)}
                                      title=${
                                      u.is_broadcaster
                                        ? 'No se pueden modificar los roles del broadcaster'
                                        : 'Gestionar roles'
                                    }
                                      disabled=${isActioning || u.is_broadcaster}
                                    >
                                      <i class="fa-solid fa-user-shield"></i>
                                    </button>
                                    <button
                                      class="btn btn-secondary btn-sm"
                                      onClick=${() => handleSetNickname(u)}
                                      title="Establecer apodo"
                                      disabled=${isActioning}
                                    >
                                      <i class="fa-solid fa-pen-to-square"></i>
                                    </button>
                                    <button
                                      class="btn btn-secondary btn-sm"
                                      onClick=${() => setHistoryUser(u)}
                                      title="Ver historial de mensajes"
                                      disabled=${isActioning}
                                    >
                                      <i class="fa-solid fa-clock-rotate-left"></i>
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            `;
                          })}
                        </tbody>
                      </table>
                    `
              }
            </div>

            <!-- Barra de paginación inferior -->
            ${
              !loadingUsers && totalPages > 1
                ? html`
                    <div class="pagination-bar">
                      <div class="pagination-info">
                        Mostrando ${users.length} usuarios de ${totalUsers} encontrados
                      </div>
                      <div class="pagination-buttons">
                        <button
                          class="btn btn-secondary btn-sm btn-icon"
                          onClick=${() => setPage(p => Math.max(1, p - 1))}
                          disabled=${page === 1}
                        >
                          <i class="fa-solid fa-chevron-left"></i> Anterior
                        </button>
                        <span class="pagination-pages">
                          ${getPageNumbers(page, totalPages).map((p, i) => {
                            if (p === '...') {
                              return html`<span key=${i} class="pagination-ellipsis">...</span>`;
                            }
                            return html`
                              <button
                                key=${i}
                                class="btn btn-sm ${page === p ? 'btn-primary' : 'btn-secondary'}"
                                style="min-width: 32px; padding: 6px 4px;"
                                onClick=${() => setPage(p)}
                              >
                                ${p}
                              </button>
                            `;
                          })}
                        </span>
                        <button
                          class="btn btn-secondary btn-sm btn-icon"
                          onClick=${() => setPage(p => Math.min(totalPages, p + 1))}
                          disabled=${page === totalPages}
                        >
                          Siguiente <i class="fa-solid fa-chevron-right"></i>
                        </button>
                      </div>
                    </div>
                  `
                : null
            }
          </div>
        </div>
      </div>

      ${
        selectedUserForRoles &&
        html`
          <div class="modal-backdrop" onClick=${() => setSelectedUserForRoles(null)}>
            <div
              class="modal-card"
              style="text-align: left; max-width: 450px;"
              onClick=${e => e.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-labelledby="modal-title"
            >
              <div
                style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;"
              >
                <h3 id="modal-title" style="margin:0; font-size:18px;">Gestionar Roles</h3>
                <button
                  class="btn-close"
                  style="background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:18px; padding:4px;"
                  onClick=${() => setSelectedUserForRoles(null)}
                >
                  <i class="fa-solid fa-xmark"></i>
                </button>
              </div>

              <!-- Info del Usuario -->
              <div
                style="background:var(--surface2); border: 1px solid var(--border-2); border-radius:var(--radius-sm); padding:16px; margin-bottom:20px; display:flex; flex-direction:column; gap:8px;"
              >
                <div>
                  <span
                    style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted); display:block; margin-bottom:2px;"
                    >Usuario</span
                  >
                  <strong style="color:var(--accent-text); font-size:15px;"
                    >${selectedUserForRoles.display_name || selectedUserForRoles.username}</strong
                  >
                  ${
                    selectedUserForRoles.display_name &&
                    selectedUserForRoles.display_name.toLowerCase() !==
                      selectedUserForRoles.username.toLowerCase()
                      ? html`<span style="color:var(--text-muted); font-size:13px; margin-left:6px;"
                          >@${selectedUserForRoles.username}</span
                        >`
                      : null
                  }
                </div>

                <div>
                  <span
                    style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted); display:block; margin-bottom:2px;"
                    >Apodo</span
                  >
                  <span style="font-size:13.5px; color:var(--text-2);"
                    >${selectedUserForRoles.nickname || 'Sin apodo'}</span
                  >
                </div>

                <div>
                  <span
                    style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted); display:block; margin-bottom:2px;"
                    >Estado Seguimiento</span
                  >
                  <span style="font-size:13px;">
                    ${
                      selectedUserForRoles.is_broadcaster
                        ? html`<span class="irc-badge badge-broadcaster">Broadcaster</span>`
                        : selectedUserForRoles.is_follower
                          ? html`<span class="irc-badge badge-follower" style="margin-right:6px;"
                                >Seguidor</span
                              >
                              <span style="color:var(--text-muted);"
                                >desde ${formatDate(selectedUserForRoles.followed_at)}</span
                              >`
                          : selectedUserForRoles.unfollowed_at
                            ? html`<span
                                  class="irc-badge badge-unfollower"
                                  style="margin-right:6px;"
                                  >Dejó de seguir</span
                                >
                                <span style="color:var(--text-muted);"
                                  >(${formatDate(selectedUserForRoles.unfollowed_at)})</span
                                >`
                            : html`<span class="irc-badge badge-never-follower"
                                >Nunca ha seguido</span
                              >`
                    }
                  </span>
                </div>
              </div>

              <!-- Listado de Roles (Toggles) -->
              <div style="display:flex; flex-direction:column; gap:12px; margin-bottom:24px;">
                <span
                  style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted); letter-spacing:0.05em;"
                  >Asignar Roles</span
                >

                <!-- Fila: Moderador -->
                <div
                  style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--border-2);"
                >
                  <div style="display:flex; align-items:center; gap:10px;">
                    <span class="irc-badge badge-moderator" style="width:50px; text-align:center;"
                      >Mod</span
                    >
                    <span style="font-size:13.5px; color:var(--text);">Moderador</span>
                  </div>
                  <input
                    type="checkbox"
                    class="role-toggle-checkbox"
                    checked=${tempRoles.is_moderator}
                    onChange=${e => setTempRoles({ ...tempRoles, is_moderator: e.target.checked })}
                  />
                </div>

                <!-- Fila: VIP -->
                <div
                  style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--border-2);"
                >
                  <div style="display:flex; align-items:center; gap:10px;">
                    <span class="irc-badge badge-vip" style="width:50px; text-align:center;"
                      >VIP</span
                    >
                    <span style="font-size:13.5px; color:var(--text);">VIP</span>
                  </div>
                  <input
                    type="checkbox"
                    class="role-toggle-checkbox"
                    checked=${tempRoles.is_vip}
                    onChange=${e => setTempRoles({ ...tempRoles, is_vip: e.target.checked })}
                  />
                </div>

                <!-- Fila: Bot -->
                <div
                  style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--border-2);"
                >
                  <div style="display:flex; align-items:center; gap:10px;">
                    <span class="irc-badge badge-bot" style="width:50px; text-align:center;"
                      >Bot</span
                    >
                    <span style="font-size:13.5px; color:var(--text);">Bot de chat</span>
                  </div>
                  <input
                    type="checkbox"
                    class="role-toggle-checkbox"
                    checked=${tempRoles.is_bot}
                    onChange=${e => setTempRoles({ ...tempRoles, is_bot: e.target.checked })}
                  />
                </div>
              </div>

              <!-- Acciones -->
              <div class="modal-actions">
                <button class="btn btn-secondary" onClick=${() => setSelectedUserForRoles(null)}>
                  Cancelar
                </button>
                <button class="btn btn-primary" onClick=${handleSaveRoles}>Guardar</button>
              </div>
            </div>
          </div>
        `
      }
    </div>

    ${
      historyUser
        ? html`<${UserHistoryDrawer} user=${historyUser} onClose=${() => setHistoryUser(null)} />`
        : null
    }
  `;
}
