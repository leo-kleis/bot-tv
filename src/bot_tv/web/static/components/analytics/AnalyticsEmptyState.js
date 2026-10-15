import { html } from 'preact-setup';

export function AnalyticsEmptyState({ message, description, onRefresh }) {
  return html`
    <div class="analytics-empty-state">
      <div class="analytics-empty-icon-wrap">
        <i class="fas fa-chart-line"></i>
      </div>
      <h3 class="analytics-empty-title">${message || 'No hay datos de analíticas disponibles'}</h3>
      <p class="analytics-empty-desc">
        ${
          description ||
          'Las estadísticas se generarán automáticamente a medida que se transmitan sesiones o se registre actividad en el chat.'
        }
      </p>
      ${
        onRefresh
          ? html`
              <button class="analytics-empty-btn" onClick=${onRefresh}>
                <i class="fas fa-sync-alt"></i>
                <span>Comprobar nuevamente</span>
              </button>
            `
          : null
      }
    </div>
  `;
}
