import { html } from 'preact-setup';

export function ChatHeaderButton({
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
      id=${id}
      class="chat-header-btn ${loading ? 'is-loading' : ''}"
      onClick=${onClick}
      disabled=${disabled || loading}
      title=${title}
    >
      ${
        loading
          ? html`<i class="fa-solid fa-spinner fa-spin"></i>`
          : html`<i class="fa-solid ${icon}"></i>`
      }
      <span>${label}</span>
    </button>
  `;
}
