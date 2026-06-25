import { html } from 'preact-setup';
import { getEventDetails } from './event-config.js';

export function ToastOverlay({ toasts, dispatch }) {
  if (!toasts || toasts.length === 0) return null;

  return html`
    <div class="toast-overlay">
      ${toasts.map(toast => {
        const details = getEventDetails(toast.type);
        return html`
          <div key=${toast.id} class="toast-card ${details.toastClassName}">
            <div class="toast-icon">
              <i class="fa-solid ${details.icon}"></i>
            </div>
            <div class="toast-content">
              <div class="toast-title">${details.toastTitle}</div>
              <div class="toast-text">${details.toastText(toast.data)}</div>
            </div>
            <button
              class="toast-close"
              onClick=${() => dispatch({ type: 'REMOVE_TOAST', id: toast.id })}
            >
              <i class="fa-solid fa-xmark"></i>
            </button>
          </div>
        `;
      })}
    </div>
  `;
}
