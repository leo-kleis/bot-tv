// Mapeo centralizado de tipo de evento Twitch a configuraciones de visualización en Chat y Toasts.
export const EVENT_CONFIG = {
  twitch_raid: {
    icon: 'fa-people-group',
    sysClassName: 'sys-raid',
    toastClassName: 'toast-raid',
    toastTitle: '¡Raid Recibida!',
    chatHtml: (data, html) =>
      html`<strong>${data.from_display_name}</strong> nos hizo raid con
        <strong>${data.viewer_count}</strong> espectadores!`,
    toastText: data => `${data.from_display_name} nos trajo a ${data.viewer_count} espectadores.`,
  },
  twitch_subscribe: {
    icon: 'fa-star',
    sysClassName: 'sys-sub',
    toastClassName: 'toast-sub',
    toastTitle: '¡Nueva Suscripción!',
    chatHtml: (data, html) => {
      const regalo = data.is_gift ? ' (Regalo)' : '';
      return html`<strong>${data.display_name}</strong> se suscribió en Tier
        <strong>${data.tier}</strong>${regalo}!`;
    },
    toastText: data => {
      const regalo = data.is_gift ? ' (Regalo)' : '';
      return `${data.display_name} se suscribió en Tier ${data.tier}${regalo}.`;
    },
  },
  twitch_sub_gift: {
    icon: 'fa-gift',
    sysClassName: 'sys-sub-gift',
    toastClassName: 'toast-sub-gift',
    toastTitle: '¡Suscripciones Regaladas!',
    chatHtml: (data, html) => {
      const donante = data.is_anonymous ? 'Anónimo' : data.display_name;
      const acum = data.cumulative_total ? ` (Total: ${data.cumulative_total})` : '';
      return html`<strong>${donante}</strong> regaló <strong>${data.total}</strong> subs de Tier
        <strong>${data.tier}</strong>${acum}!`;
    },
    toastText: data => {
      const donante = data.is_anonymous ? 'Un donante anónimo' : data.display_name;
      const acum = data.cumulative_total ? ` (Total: ${data.cumulative_total})` : '';
      return `${donante} regaló ${data.total} subs de Tier ${data.tier}${acum}!`;
    },
  },
  twitch_sub_message: {
    icon: 'fa-comments',
    sysClassName: 'sys-sub-resub',
    toastClassName: 'toast-sub-resub',
    toastTitle: '¡Resuscripción!',
    chatHtml: (data, html) => {
      const msgStr = data.message ? ` - "${data.message}"` : '';
      const rachaStr = data.streak_months ? ` (Racha: ${data.streak_months} meses)` : '';
      return html`<strong>${data.display_name}</strong> se resuscribió por
        <strong>${data.cumulative_months}</strong> meses${rachaStr}!${msgStr}`;
    },
    toastText: data => {
      const msgStr = data.message ? `: "${data.message}"` : '.';
      const rachaStr = data.streak_months ? ` (Racha: ${data.streak_months} meses)` : '';
      return `${data.display_name} se resuscribió por ${data.cumulative_months} meses${rachaStr}${msgStr}`;
    },
  },
  twitch_cheer: {
    icon: 'fa-gem',
    sysClassName: 'sys-cheer',
    toastClassName: 'toast-cheer',
    toastTitle: '¡Cheer con Bits!',
    chatHtml: (data, html) => {
      const cheerDonante = data.is_anonymous ? 'Anónimo' : data.display_name;
      const cheerMsg = data.message ? ` - "${data.message}"` : '';
      return html`<strong>${cheerDonante}</strong> envió
        <strong>${data.bits}</strong> bits!${cheerMsg}`;
    },
    toastText: data => {
      const cheerDonante = data.is_anonymous ? 'Anónimo' : data.display_name;
      const cheerMsg = data.message ? `: "${data.message}"` : '.';
      return `${cheerDonante} envió ${data.bits} bits${cheerMsg}`;
    },
  },
  twitch_points_redeem: {
    icon: 'fa-ticket',
    sysClassName: 'sys-points',
    toastClassName: 'toast-points',
    toastTitle: '¡Canje de Puntos!',
    chatHtml: (data, html) => {
      const inputStr = data.user_input ? ` ("${data.user_input}")` : '';
      return html`<strong>${data.display_name}</strong> canjeó
        <strong>${data.reward_title}</strong> por
        <strong>${data.reward_cost}</strong> puntos!${inputStr}`;
    },
    toastText: data => {
      const inputStr = data.user_input ? ` ("${data.user_input}")` : '';
      return `${data.display_name} canjeó ${data.reward_title} por ${data.reward_cost} pts${inputStr}`;
    },
  },
  prediction_begin: {
    icon: 'fa-circle-question',
    sysClassName: 'sys-prediction',
    toastClassName: 'toast-prediction',
    toastTitle: '¡Predicción Iniciada!',
    chatHtml: (data, html) =>
      html`Predicción iniciada: "<strong>${data.title}</strong>" - Opciones:
      ${data.outcomes.join(', ')}`,
    toastText: data => `"${data.title}" - Opciones: ${data.outcomes.join(', ')}`,
  },
  prediction_lock: {
    icon: 'fa-lock',
    sysClassName: 'sys-prediction',
    toastClassName: 'toast-prediction',
    toastTitle: '¡Apuestas Cerradas!',
    chatHtml: (data, html) => html`Apuestas cerradas para: "<strong>${data.title}</strong>"`,
    toastText: data => `Las apuestas de la predicción "${data.title}" se han cerrado.`,
  },
  prediction_end: {
    icon: 'fa-flag-checkered',
    sysClassName: 'sys-prediction',
    toastClassName: 'toast-prediction',
    toastTitle: '¡Predicción Finalizada!',
    chatHtml: (data, html) => {
      const resultado = data.winning_outcome_title
        ? html`Ganador: <strong>${data.winning_outcome_title}</strong>`
        : `Estado: ${data.status}`;
      return html`Predicción finalizada: "<strong>${data.title}</strong>" - ${resultado}`;
    },
    toastText: data => {
      const resultado = data.winning_outcome_title
        ? `Ganador: ${data.winning_outcome_title}`
        : `Estado: ${data.status}`;
      return `"${data.title}" - ${resultado}`;
    },
  },
  twitch_ban: {
    icon: 'fa-ban',
    sysClassName: 'sys-mod',
    toastClassName: 'toast-mod',
    toastTitle: 'Usuario Sancionado',
    chatHtml: (data, html) => {
      const tipo = data.permanent ? 'Baneo permanente' : `Timeout de ${data.duration_seconds}s`;
      const razon = data.reason ? ` (Razón: "${data.reason}")` : '';
      return html`<strong>${data.display_name}</strong> sancionado (${tipo}) por
        <strong>${data.moderator_name}</strong>${razon}.`;
    },
    toastText: data => {
      const tipo = data.permanent ? 'Baneo permanente' : `Timeout de ${data.duration_seconds}s`;
      const razon = data.reason ? ` (Razón: "${data.reason}")` : '';
      return `${data.display_name} recibió un ${tipo} por ${data.moderator_name}${razon}.`;
    },
  },
  twitch_unban: {
    icon: 'fa-key',
    sysClassName: 'sys-mod-green',
    toastClassName: 'toast-mod-green',
    toastTitle: 'Usuario Desbaneado',
    chatHtml: (data, html) =>
      html`<strong>${data.display_name}</strong> desbaneado por
        <strong>${data.moderator_name}</strong>.`,
    toastText: data =>
      `${data.display_name} fue desbaneado por el moderador ${data.moderator_name}.`,
  },
  twitch_chat_clear: {
    icon: 'fa-trash-can',
    sysClassName: 'sys-mod',
    toastClassName: 'toast-mod',
    toastTitle: 'Chat Limpiado',
    chatHtml: () => 'El chat fue limpiado por un moderador.',
    toastText: () => 'Un moderador borró todos los mensajes del chat.',
  },
  twitch_chat_clear_user: {
    icon: 'fa-broom',
    sysClassName: 'sys-mod',
    toastClassName: 'toast-mod',
    toastTitle: 'Mensajes Purgados',
    chatHtml: (data, html) =>
      html`Los mensajes de <strong>${data.display_name}</strong> fueron eliminados por un moderador.`,
    toastText: data => `Los mensajes de ${data.display_name} fueron eliminados por un moderador.`,
  },
  twitch_message_delete: {
    icon: 'fa-eraser',
    sysClassName: 'sys-mod',
    toastClassName: 'toast-mod',
    toastTitle: 'Mensaje Eliminado',
    chatHtml: (data, html) => html`Se eliminó un mensaje de <strong>${data.display_name}</strong>.`,
    toastText: data => `Se borró un mensaje del usuario ${data.display_name}.`,
  },
  api_success: {
    icon: 'fa-circle-check',
    sysClassName: 'sys-mod-green',
    toastClassName: 'toast-mod-green',
    toastTitle: 'Éxito',
    chatHtml: (data, html) => html`${data.message}`,
    toastText: data => data.message,
  },
  api_error: {
    icon: 'fa-circle-exclamation',
    sysClassName: 'sys-mod',
    toastClassName: 'toast-mod',
    toastTitle: 'Error',
    chatHtml: (data, html) => html`${data.message}`,
    toastText: data => data.message,
  },
};

export const DEFAULT_CONFIG = {
  icon: 'fa-bell',
  sysClassName: 'sys-default',
  toastClassName: '',
  toastTitle: 'Notificación',
  chatHtml: () => 'Alerta del sistema recibida.',
  toastText: () => 'Se recibió un evento de Twitch.',
};

export function getEventDetails(type) {
  return EVENT_CONFIG[type] || DEFAULT_CONFIG;
}
