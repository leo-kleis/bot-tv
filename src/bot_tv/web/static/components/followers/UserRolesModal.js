import { html, useEffect, useRef } from 'preact-setup';
import { formatDate } from './followersUtils.js';

const FOCUSABLE_SELECTOR =
  'a[href], area[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusableElements(container) {
  if (!container) return [];
  const elements = Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR));
  return elements.filter(
    el => el.offsetWidth > 0 || el.offsetHeight > 0 || el.getClientRects().length > 0
  );
}

function trapFocus(container, e) {
  if (e.key !== 'Tab') return;

  const focusables = getFocusableElements(container);
  if (focusables.length === 0) {
    e.preventDefault();
    return;
  }

  const first = focusables[0];
  const last = focusables[focusables.length - 1];

  if (e.shiftKey) {
    if (document.activeElement === first || !container.contains(document.activeElement)) {
      e.preventDefault();
      last.focus();
    }
  } else {
    if (document.activeElement === last || !container.contains(document.activeElement)) {
      e.preventDefault();
      first.focus();
    }
  }
}

function setupInertIsolation(modalElement) {
  if (!modalElement) return () => {};

  const inertedElements = [];
  const appRoot = document.getElementById('app-root');

  if (appRoot && !appRoot.contains(modalElement)) {
    if (!appRoot.hasAttribute('inert')) {
      appRoot.setAttribute('inert', '');
      inertedElements.push(appRoot);
    }
  } else {
    let current = modalElement;
    while (current && current !== document.body && current !== document.documentElement) {
      const parent = current.parentElement;
      if (parent) {
        for (const child of parent.children) {
          if (
            child !== current &&
            !child.contains(modalElement) &&
            child.id !== 'stream-category-portal'
          ) {
            if (!child.hasAttribute('inert')) {
              child.setAttribute('inert', '');
              inertedElements.push(child);
            }
          }
        }
      }
      current = parent;
    }
  }

  return () => {
    for (const el of inertedElements) {
      if (el && typeof el.removeAttribute === 'function') {
        el.removeAttribute('inert');
      }
    }
  };
}

export function UserRolesModal({ user, tempRoles, setTempRoles, onClose, onSave }) {
  const modalRef = useRef(null);
  const cardRef = useRef(null);
  const triggerRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!user) return;

    // Guardar foco previo
    triggerRef.current = document.activeElement;

    // Aislamiento inert de elementos de fondo
    const restoreInert = setupInertIsolation(modalRef.current);

    // Mover foco inicial al primer elemento accionable (botón cerrar)
    const focusTimer = requestAnimationFrame(() => {
      if (!cardRef.current) return;
      const firstFocusable = getFocusableElements(cardRef.current)[0];
      if (firstFocusable) {
        firstFocusable.focus();
      }
    });

    // Control de tecla Esc y foco en ciclo
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        if (onCloseRef.current) {
          e.preventDefault();
          e.stopPropagation();
          onCloseRef.current();
        }
        return;
      }

      if (e.key === 'Tab') {
        trapFocus(cardRef.current, e);
      }
    }

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      cancelAnimationFrame(focusTimer);
      window.removeEventListener('keydown', handleKeyDown);
      restoreInert();

      // Restaurar foco al disparador previo
      const prevEl = triggerRef.current;
      if (prevEl && typeof prevEl.focus === 'function' && document.body.contains(prevEl)) {
        prevEl.focus();
      }
    };
  }, [user]);

  if (!user) return null;

  return html`
    <div class="modal-backdrop" ref=${modalRef} onClick=${() => onClose && onClose()}>
      <div
        class="modal-card"
        ref=${cardRef}
        style="text-align: left; max-width: 450px;"
        onClick=${e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="user-roles-modal-title"
        aria-describedby="user-roles-modal-desc"
      >
        <div
          style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;"
        >
          <h3 id="user-roles-modal-title" style="margin:0; font-size:18px;">Gestionar Roles</h3>
          <button
            class="btn-close"
            style="background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:18px; padding:4px; min-width:32px; min-height:32px; display:flex; align-items:center; justify-content:center; border-radius:var(--radius-xs);"
            onClick=${onClose}
            aria-label="Cerrar modal"
          >
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>

        <!-- Info del Usuario -->
        <div id="user-roles-modal-desc" class="modal-info-box">
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
              aria-label="Rol Moderador"
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
              aria-label="Rol VIP"
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
              aria-label="Rol Bot de chat"
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
