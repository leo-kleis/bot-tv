import { html } from 'preact-setup';
import { getEventDetails } from './event-config.js';

export function ToastOverlay({ toasts, dispatch }) {
  if (!toasts || toasts.length === 0) return null;

  // Filtrar para que solo aparezcan toasts en caso de error o problema
  const errorToasts = toasts.filter(toast => {
    if (!toast) return false;
    const type = (toast.type || '').toLowerCase();
    return (
      type === 'api_error' ||
      type === 'error' ||
      type === 'warning' ||
      type === 'danger' ||
      toast.isError === true ||
      toast.isWarning === true
    );
  });

  if (errorToasts.length === 0) return null;

  return html`
    <div class="toast-overlay" role="region" aria-label="Notificaciones de error">
      ${errorToasts.map(toast => {
        const details = getEventDetails(toast.type);
        return html`
          <div
            key=${toast.id}
            class="toast-card ${details.toastClassName || 'toast-mod'}"
            role="alert"
            aria-live="assertive"
            aria-atomic="true"
          >
            <div class="toast-icon">
              <i class="fa-solid ${details.icon || 'fa-circle-exclamation'}"></i>
            </div>
            <div class="toast-content">
              <div class="toast-title">${details.toastTitle || 'Error'}</div>
              <div class="toast-text">${details.toastText(toast.data)}</div>
            </div>
            <button
              class="toast-close"
              aria-label="Cerrar notificación"
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
