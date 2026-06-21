import { h } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';

const html = htm.bind(h);

function getToastDetails(toast) {
  const type = toast.type;
  const data = toast.data;

  switch (type) {
    case 'twitch_raid':
      return {
        icon: 'fa-people-group',
        title: '¡Raid Recibida!',
        text: `${data.from_display_name} nos trajo a ${data.viewer_count} espectadores.`,
        className: 'toast-raid',
      };
    case 'twitch_subscribe':
      const regalo = data.is_gift ? ' (Regalo)' : '';
      return {
        icon: 'fa-star',
        title: '¡Nueva Suscripción!',
        text: `${data.display_name} se suscribió en Tier ${data.tier}${regalo}.`,
        className: 'toast-sub',
      };
    case 'twitch_sub_gift':
      const donante = data.is_anonymous ? 'Un donante anónimo' : data.display_name;
      const acum = data.cumulative_total ? ` (Total: ${data.cumulative_total})` : '';
      return {
        icon: 'fa-gift',
        title: '¡Suscripciones Regaladas!',
        text: `${donante} regaló ${data.total} subs de Tier ${data.tier}${acum}!`,
        className: 'toast-sub-gift',
      };
    case 'twitch_sub_message':
      const msgStr = data.message ? `: "${data.message}"` : '.';
      const rachaStr = data.streak_months ? ` (Racha: ${data.streak_months} meses)` : '';
      return {
        icon: 'fa-comments',
        title: '¡Resuscripción!',
        text: `${data.display_name} se resuscribió por ${data.cumulative_months} meses${rachaStr}${msgStr}`,
        className: 'toast-sub-resub',
      };
    case 'twitch_cheer':
      const cheerDonante = data.is_anonymous ? 'Anónimo' : data.display_name;
      const cheerMsg = data.message ? `: "${data.message}"` : '.';
      return {
        icon: 'fa-gem',
        title: '¡Cheer con Bits!',
        text: `${cheerDonante} envió ${data.bits} bits${cheerMsg}`,
        className: 'toast-cheer',
      };
    case 'twitch_points_redeem':
      const inputStr = data.user_input ? ` ("${data.user_input}")` : '';
      return {
        icon: 'fa-ticket',
        title: '¡Canje de Puntos!',
        text: `${data.display_name} canjeó ${data.reward_title} por ${data.reward_cost} pts${inputStr}`,
        className: 'toast-points',
      };
    case 'prediction_begin':
      const opciones = data.outcomes.join(', ');
      return {
        icon: 'fa-circle-question',
        title: '¡Predicción Iniciada!',
        text: `"${data.title}" - Opciones: ${opciones}`,
        className: 'toast-prediction',
      };
    case 'prediction_lock':
      return {
        icon: 'fa-lock',
        title: '¡Apuestas Cerradas!',
        text: `Las apuestas de la predicción "${data.title}" se han cerrado.`,
        className: 'toast-prediction',
      };
    case 'prediction_end':
      const resultado = data.winning_outcome_title 
        ? `Ganador: ${data.winning_outcome_title}` 
        : `Estado: ${data.status}`;
      return {
        icon: 'fa-flag-checkered',
        title: '¡Predicción Finalizada!',
        text: `"${data.title}" - ${resultado}`,
        className: 'toast-prediction',
      };
    case 'twitch_ban':
      const tipo = data.permanent ? 'Baneo permanente' : `Timeout de ${data.duration_seconds}s`;
      const razon = data.reason ? ` (Razón: "${data.reason}")` : '';
      return {
        icon: 'fa-ban',
        title: 'Usuario Sancionado',
        text: `${data.display_name} recibió un ${tipo} por ${data.moderator_name}${razon}.`,
        className: 'toast-mod',
      };
    case 'twitch_unban':
      return {
        icon: 'fa-key',
        title: 'Usuario Desbaneado',
        text: `${data.display_name} fue desbaneado por el moderador ${data.moderator_name}.`,
        className: 'toast-mod-green',
      };
    case 'twitch_chat_clear':
      return {
        icon: 'fa-trash-can',
        title: 'Chat Limpiado',
        text: 'Un moderador borró todos los mensajes del chat.',
        className: 'toast-mod',
      };
    case 'twitch_chat_clear_user':
      return {
        icon: 'fa-broom',
        title: 'Mensajes Purgados',
        text: `Los mensajes de ${data.display_name} fueron eliminados por un moderador.`,
        className: 'toast-mod',
      };
    case 'twitch_message_delete':
      return {
        icon: 'fa-eraser',
        title: 'Mensaje Eliminado',
        text: `Se borró un mensaje del usuario ${data.display_name}.`,
        className: 'toast-mod',
      };
    default:
      return {
        icon: 'fa-bell',
        title: 'Notificación',
        text: 'Se recibió un evento de Twitch.',
        className: '',
      };
  }
}

export function ToastOverlay({ toasts, dispatch }) {
  if (!toasts || toasts.length === 0) return null;

  return html`
    <div class="toast-overlay">
      ${toasts.map((toast) => {
        const details = getToastDetails(toast);
        return html`
          <div key=${toast.id} class="toast-card ${details.className}">
            <div class="toast-icon">
              <i class="fa-solid ${details.icon}"></i>
            </div>
            <div class="toast-content">
              <div class="toast-title">${details.title}</div>
              <div class="toast-text">${details.text}</div>
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
