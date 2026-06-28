import { html, useState, useEffect, useRef } from 'preact-setup';
import { apiPost, apiGet } from '/static/components/api.js';
import { CustomSelect } from '/static/components/CustomSelect.js';

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

const SELECT_OPTIONS = [
  { value: 'all', label: 'Todos los usuarios' },
  { value: 'follower', label: 'Seguidor' },
  { value: 'not_follower', label: 'No Seguidor' },
  { value: 'unfollower', label: 'Dejó de Seguir' },
];

export function FollowersTab({ followers }) {
  const [syncing, setSyncing] = useState(false);
  const [result, setResult] = useState(null);

  // Estados para filtros de listado de usuarios
  const [nameInput, setNameInput] = useState('');
  const [nameSearch, setNameSearch] = useState('');
  const [isFollower, setIsFollower] = useState('all'); // 'all', 'true', 'false'
  const [followedAfter, setFollowedAfter] = useState('');
  const [followedBefore, setFollowedBefore] = useState('');
  const [unfollowedAfter, setUnfollowedAfter] = useState('');
  const [unfollowedBefore, setUnfollowedBefore] = useState('');

  // Estados de paginación y carga
  const [users, setUsers] = useState([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [page, setPage] = useState(1);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(null); // trackea acciones rápidas por usuario

  const limit = 50;
  const sync = followers.lastSync;
  const prog = followers.progress;

  // Ref para almacenar filtros anteriores y prevenir doble fetch
  const prevFilters = useRef({
    nameSearch,
    isFollower,
    followedAfter,
    followedBefore,
    unfollowedAfter,
    unfollowedBefore,
  });

  // Debounce del buscador de nombre (350ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setNameSearch(nameInput);
    }, 350);
    return () => clearTimeout(timer);
  }, [nameInput]);

  // Efecto que controla la carga al cambiar filtros o paginar
  useEffect(() => {
    const filtersChanged =
      prevFilters.current.nameSearch !== nameSearch ||
      prevFilters.current.isFollower !== isFollower ||
      prevFilters.current.followedAfter !== followedAfter ||
      prevFilters.current.followedBefore !== followedBefore ||
      prevFilters.current.unfollowedAfter !== unfollowedAfter ||
      prevFilters.current.unfollowedBefore !== unfollowedBefore;

    prevFilters.current = {
      nameSearch,
      isFollower,
      followedAfter,
      followedBefore,
      unfollowedAfter,
      unfollowedBefore,
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
    followedAfter,
    followedBefore,
    unfollowedAfter,
    unfollowedBefore,
  ]);

  async function fetchUsers() {
    setLoadingUsers(true);
    const params = new window.URLSearchParams();
    if (nameSearch.trim()) params.append('name', nameSearch.trim());
    if (isFollower !== 'all') params.append('is_follower', isFollower);
    if (followedAfter) params.append('followed_after', followedAfter);
    if (followedBefore) params.append('followed_before', followedBefore);
    if (unfollowedAfter) params.append('unfollowed_after', unfollowedAfter);
    if (unfollowedBefore) params.append('unfollowed_before', unfollowedBefore);
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

  async function handleSync() {
    setSyncing(true);
    setResult(null);
    const data = await apiPost('/api/sync_followers', {});
    setSyncing(false);
    if (data.ok) {
      setResult({ ok: true, msg: 'Sincronización completada.' });
      fetchUsers(); // Actualizar listado tras sincronizar
    } else {
      setResult({ ok: false, msg: data.error || 'Error al sincronizar.' });
    }
  }

  // Acciones rápidas sobre los usuarios de la tabla
  async function handleToggleBot(u) {
    setActionInProgress(u.username);
    const res = await apiPost('/api/toggle_bot', { username: u.username });
    setActionInProgress(null);
    if (res && res.ok) {
      fetchUsers();
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
    setFollowedAfter('');
    setFollowedBefore('');
    setUnfollowedAfter('');
    setUnfollowedBefore('');
    setPage(1);
  }

  const progPct = prog ? Math.round((prog.count / prog.total) * 100) : 0;
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
                  <div class="stat-value">${sync?.new_count ?? '—'}</div>
                  <div class="stat-label">Nuevos</div>
                </div>
                <div class="stat-card lost">
                  <div class="stat-value">${sync?.lost_count ?? '—'}</div>
                  <div class="stat-label">Perdidos</div>
                </div>
              </div>

              ${prog
                ? html`
                    <div>
                      <div class="progress-text" style="margin-bottom:6px">
                        ${prog.count} / ${prog.total} seguidores
                      </div>
                      <div class="progress-bar-wrap">
                        <div class="progress-bar-fill" style="width:${progPct}%"></div>
                      </div>
                    </div>
                  `
                : null}

              <button
                id="btn-sync-followers"
                class="btn btn-primary"
                style="width:100%"
                onClick=${handleSync}
                disabled=${syncing}
              >
                ${syncing
                  ? html`<span class="spinner"></span> Sincronizando...`
                  : html`<i class="fa-solid fa-rotate"></i> Sincronizar ahora`}
              </button>

              ${result
                ? html`<div class="result-msg ${result.ok ? 'ok' : 'err'}">${result.msg}</div>`
                : null}
            </div>
          </div>

          ${!sync
            ? html`
                <div style="text-align:center;color:var(--text-muted);font-size:13px;padding:20px">
                  Sin datos de sync. Presiona "Sincronizar ahora" o espera la sincronización
                  automática al iniciar.
                </div>
              `
            : null}
        </div>

        <!-- Columna Derecha: Nuevos y Perdidos del último sync -->
        ${sync?.new_labels?.length > 0 || sync?.lost_labels?.length > 0
          ? html`
              <div class="two-col">
                <!-- Nuevos seguidores -->
                ${sync.new_labels.length > 0
                  ? html`
                      <div class="section">
                        <div class="section-header" style="color:var(--success)">
                          <span class="section-icon"><i class="fa-solid fa-user-plus"></i></span>
                          Nuevos (${sync.new_count})
                        </div>
                        <div class="section-body">
                          <div class="follower-list">
                            ${sync.new_labels.map(
                              (l, i) => html`<div key=${i} class="follower-item new">${l}</div>`
                            )}
                          </div>
                        </div>
                      </div>
                    `
                  : null}

                <!-- Perdidos -->
                ${sync.lost_labels.length > 0
                  ? html`
                      <div class="section">
                        <div class="section-header" style="color:var(--danger)">
                          <span class="section-icon"><i class="fa-solid fa-user-minus"></i></span>
                          Dejaron de seguir (${sync.lost_count})
                        </div>
                        <div class="section-body">
                          <div class="follower-list">
                            ${sync.lost_labels.map(
                              (l, i) => html`<div key=${i} class="follower-item lost">${l}</div>`
                            )}
                          </div>
                        </div>
                      </div>
                    `
                  : null}
              </div>
            `
          : null}
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
          ${!loadingUsers && totalUsers > 0
            ? html`
                <span style="font-size: 12px; color: var(--text-muted); font-weight: normal;">
                  Total: <strong style="color: var(--accent-text);">${totalUsers}</strong> usuarios
                  encontrados
                </span>
              `
            : null}
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

            <!-- Rango Fecha Seguimiento -->
            <div class="filter-group">
              <label class="filter-label">Seguidor desde</label>
              <div class="filter-dates-row">
                <input
                  type="date"
                  value=${followedAfter}
                  onChange=${e => setFollowedAfter(e.target.value)}
                  placeholder="Desde"
                  disabled=${isFollower === 'not_follower'}
                />
                <span class="filter-separator">a</span>
                <input
                  type="date"
                  value=${followedBefore}
                  onChange=${e => setFollowedBefore(e.target.value)}
                  placeholder="Hasta"
                  disabled=${isFollower === 'not_follower'}
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
                  onChange=${e => setUnfollowedAfter(e.target.value)}
                  placeholder="Desde"
                  disabled=${isFollower === 'follower' || isFollower === 'not_follower'}
                />
                <span class="filter-separator">a</span>
                <input
                  type="date"
                  value=${unfollowedBefore}
                  onChange=${e => setUnfollowedBefore(e.target.value)}
                  placeholder="Hasta"
                  disabled=${isFollower === 'follower' || isFollower === 'not_follower'}
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
              ${loadingUsers &&
              html`
                <div class="table-loading-overlay">
                  <span class="spinner"></span> Cargando usuarios...
                </div>
              `}
              ${users.length === 0
                ? html`<div class="empty-table" style="border-bottom: 1px solid var(--border-2);">
                    No se encontraron usuarios con los filtros seleccionados.
                  </div>`
                : html`
                    <table class="users-table">
                      <thead>
                        <tr>
                          <th>Usuario</th>
                          <th>Roles</th>
                          <th>Estado Seguimiento</th>
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
                                  ${u.nickname ||
                                  (u.display_name &&
                                    u.display_name.toLowerCase() !== u.username.toLowerCase())
                                    ? html`
                                        <div class="user-sub-names">
                                          ${u.nickname
                                            ? html`<span class="user-nickname-tag"
                                                ><i class="fa-solid fa-signature"></i>
                                                ${u.nickname}</span
                                              >`
                                            : null}
                                          ${u.display_name &&
                                          u.display_name.toLowerCase() !== u.username.toLowerCase()
                                            ? html`<span>@${u.username}</span>`
                                            : null}
                                        </div>
                                      `
                                    : null}
                                </div>
                              </td>

                              <!-- Roles -->
                              <td data-label="Roles">
                                <div class="irc-user-badges">
                                  ${u.is_moderator
                                    ? html`<span class="irc-badge badge-moderator">Mod</span>`
                                    : null}
                                  ${u.is_vip
                                    ? html`<span class="irc-badge badge-vip">VIP</span>`
                                    : null}
                                  ${u.is_subscriber
                                    ? html`<span class="irc-badge badge-subscriber">Sub</span>`
                                    : null}
                                  ${u.is_bot
                                    ? html`<span class="irc-badge badge-bot">Bot</span>`
                                    : null}
                                </div>
                              </td>

                              <!-- Estado Seguimiento -->
                              <td data-label="Seguimiento">
                                ${u.is_broadcaster
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
                                        >`}
                              </td>

                              <!-- Acciones rápidas -->
                              <td data-label="Acciones">
                                <div class="user-table-actions">
                                  <button
                                    class="btn btn-secondary btn-sm ${u.is_bot
                                      ? 'active-bot-btn'
                                      : ''}"
                                    onClick=${() => handleToggleBot(u)}
                                    title=${u.is_bot ? 'Desmarcar como bot' : 'Marcar como bot'}
                                    disabled=${isActioning}
                                  >
                                    <i class="fa-solid fa-robot"></i>
                                  </button>
                                  <button
                                    class="btn btn-secondary btn-sm"
                                    onClick=${() => handleSetNickname(u)}
                                    title="Establecer apodo"
                                    disabled=${isActioning}
                                  >
                                    <i class="fa-solid fa-pen-to-square"></i>
                                  </button>
                                </div>
                              </td>
                            </tr>
                          `;
                        })}
                      </tbody>
                    </table>
                  `}
            </div>

            <!-- Barra de paginación inferior -->
            ${!loadingUsers && totalPages > 1
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
              : null}
          </div>
        </div>
      </div>
    </div>
  `;
}
