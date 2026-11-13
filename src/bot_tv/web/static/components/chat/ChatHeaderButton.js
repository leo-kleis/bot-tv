import { html, memo } from 'preact-setup';

/**
 * Botón reutilizable de acción en la cabecera del chat.
 *
 * @param {Object} props
 * @param {string} props.id
 * @param {string} props.icon
 * @param {string} props.label
 * @param {string} props.title
 * @param {boolean} [props.disabled=false]
 * @param {boolean} [props.loading=false]
 * @param {() => void} props.onClick
 */
export const ChatHeaderButton = memo(function ChatHeaderButton({
  id,
  icon,
  label,
  title,
  disabled = false,
  loading = false,
  onClick,
}) {
  return html`
    <button
      type="button"
      id=${id}
      class="chat-header-btn ${loading ? 'is-loading' : ''}"
      onClick=${onClick}
      disabled=${disabled || loading}
      title=${title}
    >
      ${
        loading
          ? html`<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i>`
          : html`<i class="fa-solid ${icon}" aria-hidden="true"></i>`
      }
      <span>${label}</span>
    </button>
  `;
});
