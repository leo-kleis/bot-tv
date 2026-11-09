import { html, useEffect } from 'preact-setup';
import { getEventDetails } from './event-config.js';

function isCriticalToast(toast) {
  if (toast.isError === true) return true;
  const type = (toast.type || '').toLowerCase();
  return type === 'api_error' || type === 'error' || type === 'danger';
}

function ToastItem({ toast, dispatch }) {
  useEffect(() => {
    const timer = setTimeout(() => {
      dispatch({ type: 'REMOVE_TOAST', id: toast.id });
    }, 6000);
    return () => clearTimeout(timer);
  }, [toast.id, dispatch]);

  const details = getEventDetails(toast.type);
  const isCritical = isCriticalToast(toast);
  const role = isCritical ? 'alert' : 'status';
  const ariaLive = isCritical ? 'assertive' : 'polite';

  return html`
    <div
      class="toast-card ${details.toastClassName || 'toast-mod'}"
      role=${role}
      aria-live=${ariaLive}
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
  // Descartar inmediatamente toasts de seguidores si se generan estando en la pestaña 'users'
  useEffect(() => {
    if (activeTab !== 'users' || !toasts || toasts.length === 0) return;
    toasts.forEach(toast => {
      if (!toast) return;
      const type = (toast.type || '').toLowerCase();
      if (type === 'follower_new' || type === 'follower_lost' || type === 'twitch_follow') {
        dispatch({ type: 'REMOVE_TOAST', id: toast.id });
      }
    });
  }, [activeTab, toasts, dispatch]);

  if (!toasts || toasts.length === 0) return null;

  const visibleToasts = toasts.filter(toast => {
    if (!toast) return false;
    const type = (toast.type || '').toLowerCase();

    // Notificaciones de seguidores solo cuando NO se está en la pestaña de usuarios
    if (type === 'follower_new' || type === 'follower_lost' || type === 'twitch_follow') {
      return activeTab !== 'users';
    }

    return (
      type === 'api_error' ||
      type === 'error' ||
      type === 'warning' ||
      type === 'danger' ||
      type === 'api_success' ||
      type === 'success' ||
      type === 'mod_action' ||
      toast.isError === true ||
      toast.isWarning === true
    );
  });

  if (visibleToasts.length === 0) return null;

  return html`
    <div class="toast-overlay" role="region" aria-label="Notificaciones del sistema">
      ${visibleToasts.map(
        toast => html`<${ToastItem} key=${toast.id} toast=${toast} dispatch=${dispatch} />`
      )}
    </div>
  `;
}
