import { html } from 'preact-setup';
import { formatDate } from './followersUtils.js';

export function UserRolesModal({ user, tempRoles, setTempRoles, onClose, onSave }) {
  if (!user) return null;

  return html`
    <div class="modal-backdrop" onClick=${onClose}>
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
            onClick=${onClose}
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
              >${user.display_name || user.username}</strong
            >
            ${
              user.display_name && user.display_name.toLowerCase() !== user.username.toLowerCase()
                ? html`<span style="color:var(--text-muted); font-size:13px; margin-left:6px;"
                    >@${user.username}</span
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
              >${user.nickname || 'Sin apodo'}</span
            >
          </div>

          <div>
            <span
              style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted); display:block; margin-bottom:2px;"
              >Estado Seguimiento</span
            >
            <span style="font-size:13px;">
              ${
                user.is_broadcaster
                  ? html`<span class="irc-badge badge-broadcaster">Broadcaster</span>`
                  : user.is_follower
                    ? html`<span class="irc-badge badge-follower" style="margin-right:6px;"
                          >Seguidor</span
                        >
                        <span style="color:var(--text-muted);"
                          >desde ${formatDate(user.followed_at)}</span
                        >`
                    : user.unfollowed_at
                      ? html`<span class="irc-badge badge-unfollower" style="margin-right:6px;"
                            >Dejó de seguir</span
                          >
                          <span style="color:var(--text-muted);"
                            >(${formatDate(user.unfollowed_at)})</span
                          >`
                      : html`<span class="irc-badge badge-never-follower">Nunca ha seguido</span>`
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
            style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--border-2); min-width:0;"
          >
            <div style="display:flex; align-items:center; gap:10px; min-width:0;">
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
            style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--border-2); min-width:0;"
          >
            <div style="display:flex; align-items:center; gap:10px; min-width:0;">
              <span class="irc-badge badge-vip" style="width:50px; text-align:center;">VIP</span>
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
            style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--border-2); min-width:0;"
          >
            <div style="display:flex; align-items:center; gap:10px; min-width:0;">
              <span class="irc-badge badge-bot" style="width:50px; text-align:center;">Bot</span>
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
          <button class="btn btn-secondary" onClick=${onClose}>Cancelar</button>
          <button class="btn btn-primary" onClick=${onSave}>Guardar</button>
        </div>
      </div>
    </div>
  `;
}
