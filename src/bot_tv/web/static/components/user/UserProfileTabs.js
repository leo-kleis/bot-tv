import { html } from 'preact-setup';
import { formatDate } from '/static/components/followers/followersUtils.js';
import { formatCount, formatTimestamp } from '/static/hooks/useMessageHistory.js';

export function UserInfoTabPanel({
  editingNick,
  setEditingNick,
  nickname,
  setNickname,
  savingNick,
  nickError,
  onSaveNickname,
  userData,
  total,
}) {
  return html`
    <div
      id="drawer-panel-info"
      role="tabpanel"
      aria-labelledby="drawer-tab-info"
      tabindex="0"
      class="history-drawer-panel"
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
                <div style="display:flex; gap:8px; min-width:0;">
                  <input
                    type="text"
                    style="flex:1; min-width:0; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius-xs); color:var(--text); padding:6px 10px; font-size:13px;"
                    value=${nickname}
                    onInput=${e => setNickname(e.target.value)}
                    placeholder="Sin apodo"
                    aria-label="Apodo en la app"
                    disabled=${savingNick}
                  />
                  <button
                    class="btn btn-primary"
                    style="padding:6px 12px; font-size:12px;"
                    onClick=${onSaveNickname}
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
                  ${
                    userData.nickname
                      ? html`<strong>${userData.nickname}</strong>`
                      : html`<em style="color:var(--text-muted);">Sin apodo asignado</em>`
                  }
                </div>
              `
        }
        ${
          nickError
            ? html`<div role="alert" style="margin-top:8px; font-size:12px; color:var(--danger);">
                ${nickError}
              </div>`
            : null
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
                    <span class="irc-badge badge-follower" style="margin-right:6px;">Seguidor</span>
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
                  : html`<span class="irc-badge badge-never-follower">Nunca ha seguido</span>`
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
  `;
}

export function UserRolesTabPanel({
  syncingRoles,
  savingRoles,
  rolesError,
  modError,
  tempRoles,
  setTempRoles,
  onSaveRoles,
  userData,
  actionInProgress,
  onOpenPurge,
  onOpenUnban,
  onOpenBan,
}) {
  return html`
    <div
      id="drawer-panel-roles"
      role="tabpanel"
      aria-labelledby="drawer-tab-roles"
      tabindex="0"
      class="history-drawer-panel roles-panel"
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
          ${
            syncingRoles
              ? html`<span style="font-size:11px; color:var(--text-muted);"
                  ><i class="fa-solid fa-spinner fa-spin"></i> Sincronizando...</span
                >`
              : null
          }
        </div>

        <div style="display:flex; flex-direction:column; gap:10px;">
          <label
            style="display:flex; justify-content:space-between; align-items:center; cursor:${
              syncingRoles || savingRoles ? 'not-allowed' : 'pointer'
            }; opacity:${syncingRoles ? '0.6' : '1'};"
          >
            <span style="font-size:13px; color:var(--text);">Moderador</span>
            <input
              type="checkbox"
              class="role-toggle-checkbox"
              checked=${tempRoles.is_moderator}
              disabled=${syncingRoles || savingRoles}
              onChange=${e => setTempRoles({ ...tempRoles, is_moderator: e.target.checked })}
            />
          </label>

          <label
            style="display:flex; justify-content:space-between; align-items:center; cursor:${
              syncingRoles || savingRoles ? 'not-allowed' : 'pointer'
            }; opacity:${syncingRoles ? '0.6' : '1'};"
          >
            <span style="font-size:13px; color:var(--text);">VIP</span>
            <input
              type="checkbox"
              class="role-toggle-checkbox"
              checked=${tempRoles.is_vip}
              disabled=${syncingRoles || savingRoles}
              onChange=${e => setTempRoles({ ...tempRoles, is_vip: e.target.checked })}
            />
          </label>

          <label
            style="display:flex; justify-content:space-between; align-items:center; cursor:${
              syncingRoles || savingRoles ? 'not-allowed' : 'pointer'
            }; opacity:${syncingRoles ? '0.6' : '1'};"
          >
            <span style="font-size:13px; color:var(--text);">Bot de Chat</span>
            <input
              type="checkbox"
              class="role-toggle-checkbox"
              checked=${tempRoles.is_bot}
              disabled=${syncingRoles || savingRoles}
              onChange=${e => setTempRoles({ ...tempRoles, is_bot: e.target.checked })}
            />
          </label>
        </div>

        <button
          class="btn btn-primary"
          style="width:100%; margin-top:14px; padding:8px;"
          onClick=${onSaveRoles}
          disabled=${syncingRoles || savingRoles}
        >
          ${
            syncingRoles
              ? html`<i class="fa-solid fa-spinner fa-spin"></i> Sincronizando roles...`
              : savingRoles
                ? html`<i class="fa-solid fa-spinner fa-spin"></i> Guardando...`
                : 'Guardar Roles'
          }
        </button>
        ${
          rolesError
            ? html`<div role="alert" style="margin-top:8px; font-size:12px; color:var(--danger);">
                ${rolesError}
              </div>`
            : null
        }
      </div>

      <!-- Acciones de Moderación Directa -->
      <div
        style="background:var(--surface2); border:1px solid var(--border-2); border-radius:var(--radius-sm); padding:14px; display:flex; flex-direction:column; gap:12px;"
      >
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span
            style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted);"
            >Acciones de Moderación</span
          >
          ${userData.is_banned ? html`<span class="irc-badge badge-banned">Baneado</span>` : null}
        </div>

        ${
          userData.is_banned &&
          (userData.ban_reason || (!userData.ban_permanent && userData.ban_expires_at))
            ? html`
                <div style="display:flex; flex-direction:column; gap:6px; padding-top:2px;">
                  ${
                    userData.ban_reason
                      ? html`
                          <div
                            style="font-size:12px; color:var(--text-muted); display:flex; justify-content:space-between; gap:12px;"
                          >
                            <span>Motivo:</span>
                            <span style="color:var(--text-2); text-align:right;"
                              >${userData.ban_reason}</span
                            >
                          </div>
                        `
                      : null
                  }
                  ${
                    !userData.ban_permanent && userData.ban_expires_at
                      ? html`
                          <div
                            style="font-size:12px; color:var(--text-muted); display:flex; justify-content:space-between; gap:12px;"
                          >
                            <span>Expira:</span>
                            <span style="color:var(--text-2); text-align:right;"
                              >${formatDate(userData.ban_expires_at)}</span
                            >
                          </div>
                        `
                      : null
                  }
                </div>
              `
            : null
        }

        <div style="display:flex; gap:10px; min-width:0;">
          <button
            class="btn"
            style="flex:1; min-width:0; background:rgba(255,255,255,0.05); border:1px solid var(--border-2); color:var(--text-2); font-size:12px; padding:10px;"
            onClick=${onOpenPurge}
            disabled=${actionInProgress}
          >
            <i class="fa-solid fa-broom" style="margin-right:6px; color:var(--warning);"></i>
            Purgar mensajes
          </button>
          ${
            userData.is_banned
              ? html`
                  <button
                    class="btn"
                    style="flex:1; min-width:0; font-size:12px; padding:10px; background:rgba(245, 158, 11, 0.15); border:1px solid rgba(245, 158, 11, 0.4); color:var(--warning);"
                    onClick=${onOpenUnban}
                    disabled=${actionInProgress}
                  >
                    <i class="fa-solid fa-user-check" style="margin-right:6px;"></i>
                    Desbanear usuario
                  </button>
                `
              : html`
                  <button
                    class="btn btn-danger"
                    style="flex:1; min-width:0; font-size:12px; padding:10px;"
                    onClick=${onOpenBan}
                    disabled=${actionInProgress}
                  >
                    <i class="fa-solid fa-ban" style="margin-right:6px;"></i> Banear usuario
                  </button>
                `
          }
        </div>
        ${
          modError
            ? html`<div role="alert" style="margin-top:4px; font-size:12px; color:var(--danger);">
                ${modError}
              </div>`
            : null
        }
      </div>
    </div>
  `;
}

export function UserHistoryTabPanel({
  searchInput,
  setSearchInput,
  since,
  setSince,
  until,
  setUntil,
  messagesRef,
  onScroll,
  loadingMore,
  hasMore,
  messages,
  loading,
}) {
  return html`
    <div
      id="drawer-panel-history"
      role="tabpanel"
      aria-labelledby="drawer-tab-history"
      tabindex="0"
      style="display:flex; flex-direction:column; flex:1; min-height:0;"
    >
      <!-- Buscador y fechas -->
      <div class="history-search">
        <div class="history-search-input-wrap">
          <i class="fa-solid fa-magnifying-glass history-search-icon"></i>
          <input
            type="text"
            class="history-search-input"
            placeholder="Buscar en mensajes..."
            aria-label="Buscar en mensajes"
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
            aria-label="Fecha desde"
          />
          <span class="history-search-sep">—</span>
          <input
            type="date"
            value=${until}
            onChange=${e => setUntil(e.target.value)}
            min=${since || ''}
            title="Hasta"
            aria-label="Fecha hasta"
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
      <div class="history-messages" ref=${messagesRef} onScroll=${onScroll}>
        ${
          loadingMore
            ? html`<div class="history-load-more">
                <span class="history-spinner"></span> Cargando anteriores...
              </div>`
            : hasMore
              ? html`<div class="history-load-more" style="color:var(--text-muted);font-size:11px;">
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
                          <span class="history-msg-time">${formatTimestamp(m.timestamp)}</span>
                          <span class="history-msg-text">${m.message || m.text}</span>
                        </div>
                      `
                    )}
                  </div>
                `
        }
      </div>
    </div>
  `;
}
