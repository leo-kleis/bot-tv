import { html } from 'preact-setup';

/**
 * Genera la inicial del nombre para el fallback visual del avatar.
 * @param {string | null | undefined} name
 * @returns {string}
 */
function getInitial(name) {
  return name ? name.charAt(0).toUpperCase() : '?';
}

/**
 * Componente de avatar de usuario reutilizable.
 *
 * @param {Object} props
 * @param {string | null | undefined} props.userId - ID del usuario para la API de avatar.
 * @param {string} props.displayName - Nombre para generar la inicial de fallback.
 * @param {string} props.color - Color RGB como string (ej: "rgb(155,92,255)") para el fondo.
 * @param {'sm' | 'md'} [props.size='md'] - Tamaño del avatar: 'sm' (18px) o 'md' (32px).
 */
export function UserAvatar({ userId, displayName, color, size = 'md' }) {
  const sizeClass = `user-avatar--${size}`;
  const avatarUrl = userId ? `/api/avatar/${encodeURIComponent(String(userId))}` : null;

  return html`
    <div class="user-avatar ${sizeClass}" style="background:${color}">
      ${
        avatarUrl &&
        html`
          <img
            src=${avatarUrl}
            alt=""
            loading="lazy"
            onError=${
              /** @param {Event} e */ e => {
                if (e.currentTarget instanceof HTMLElement) {
                  e.currentTarget.style.display = 'none';
                }
              }
            }
          />
        `
      }
      <span class="user-avatar-fallback" aria-hidden="true">${getInitial(displayName)}</span>
    </div>
  `;
}
