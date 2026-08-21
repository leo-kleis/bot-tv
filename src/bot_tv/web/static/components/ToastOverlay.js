import { html, useEffect } from 'preact-setup';
import { getEventDetails } from './event-config.js';

function ToastItem({ toast, dispatch }) {
  useEffect(() => {
    const timer = setTimeout(() => {
      dispatch({ type: 'REMOVE_TOAST', id: toast.id });
    }, 6000);
    return () => clearTimeout(timer);
  }, [toast.id, dispatch]);

  const details = getEventDetails(toast.type);

  return html`
    <div
      class="toast-card ${details.toastClassName || 'toast-mod'}"
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
    >
      <div class="toast-icon">
        <i class="fa-solid ${details.icon || 'fa-circle-exclamation'}"></i>
      </div>
      <div class="toast-content">
        <div class="toast-title">${toast.title || details.toastTitle || 'Notificación'}</div>
        <div class="toast-text">${toast.data?.message || details.toastText(toast.data)}</div>
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
}

export function ToastOverlay({ toasts, dispatch, activeTab }) {
  if (!toasts || toasts.length === 0) return null;

  const visibleToasts = toasts.filter(toast => {
    if (!toast) return false;
    const type = (toast.type || '').toLowerCase();

    // Notificaciones de seguidores solo cuando NO se está en la pestaña de usuarios
    if (type === 'follower_new' || type === 'follower_lost') {
      return activeTab !== 'users';
    }

    return (
      type === 'api_error' ||
      type === 'error' ||
      type === 'warning' ||
      type === 'danger' ||
      type === 'api_success' ||
      type === 'success' ||
      toast.isError === true ||
      toast.isWarning === true
    );
  });

  if (visibleToasts.length === 0) return null;

  return html`
    <div class="toast-overlay" role="region" aria-label="Notificaciones">
      ${visibleToasts.map(
        toast => html`<${ToastItem} key=${toast.id} toast=${toast} dispatch=${dispatch} />`
      )}
    </div>
  `;
}
