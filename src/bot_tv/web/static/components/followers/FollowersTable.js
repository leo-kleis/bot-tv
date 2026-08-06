import { html } from 'preact-setup';
import { formatDate } from './followersUtils.js';

export function FollowersTable({
  users = [],
  loadingUsers,
  sortBy,
  sortOrder,
  onSort,
  onOpenProfile,
}) {
  return html`
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
                      onClick=${() => onSort('username')}
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
                      onClick=${() => onSort('role')}
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
                      onClick=${() => onSort('follow_date')}
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
                    <th style="width: 100px; text-align: center;">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  ${users.map(u => {
                    return html`
                      <tr key=${u.user_id || u.username}>
                        <!-- Info del Usuario -->
                        <td
                          data-label="Usuario"
                          onClick=${() => onOpenProfile(u)}
                          style="cursor:pointer;"
                        >
                          <div class="user-info-cell">
                            <div class="user-display-name">${u.display_name || u.username}</div>
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
                                        u.display_name.toLowerCase() !== u.username.toLowerCase()
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
                        <td
                          data-label="Roles"
                          onClick=${() => onOpenProfile(u)}
                          style="cursor:pointer;"
                        >
                          <div class="irc-user-badges">
                            ${
                              u.is_moderator
                                ? html`<span class="irc-badge badge-moderator">Mod</span>`
                                : null
                            }
                            ${u.is_vip ? html`<span class="irc-badge badge-vip">VIP</span>` : null}
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
                            ${u.is_bot ? html`<span class="irc-badge badge-bot">Bot</span>` : null}
                          </div>
                        </td>

                        <!-- Estado Seguimiento -->
                        <td
                          data-label="Seguimiento"
                          onClick=${() => onOpenProfile(u)}
                          style="cursor:pointer;"
                        >
                          ${
                            u.is_broadcaster
                              ? html`<span class="irc-badge badge-broadcaster">Broadcaster</span>`
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

                        <!-- Acciones unificadas -->
                        <td data-label="Acción">
                          <div class="user-table-actions">
                            <button
                              class="btn btn-secondary btn-sm"
                              onClick=${() => onOpenProfile(u)}
                              title="Ver perfil y gestionar usuario"
                            >
                              <i class="fa-solid fa-user-gear"></i> Ver Perfil
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
  `;
}
