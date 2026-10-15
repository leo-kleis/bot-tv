import { html } from 'preact-setup';

export function AnalyticsSkeleton() {
  return html`
    <div class="analytics-skeleton-container" aria-busy="true" aria-label="Cargando analíticas">
      <!-- Skeleton de Tarjetas Resumen -->
      <div class="analytics-summary-grid">
        ${[1, 2, 3, 4, 5].map(
          i => html`
            <div key=${i} class="analytics-card skeleton-card">
              <div class="skeleton-header">
                <div class="skeleton-line skeleton-title"></div>
                <div class="skeleton-icon-placeholder"></div>
              </div>
              <div class="skeleton-line skeleton-value"></div>
              <div class="skeleton-line skeleton-subtitle"></div>
            </div>
          `
        )}
      </div>

      <!-- Skeleton de Gráficos -->
      <div class="analytics-charts-grid">
        <div class="analytics-chart-card skeleton-chart-card full-width">
          <div class="skeleton-header">
            <div class="skeleton-line skeleton-title"></div>
          </div>
          <div class="skeleton-chart-body"></div>
        </div>

        <div class="analytics-chart-card skeleton-chart-card">
          <div class="skeleton-header">
            <div class="skeleton-line skeleton-title"></div>
          </div>
          <div class="skeleton-chart-body"></div>
        </div>

        <div class="analytics-chart-card skeleton-chart-card">
          <div class="skeleton-header">
            <div class="skeleton-line skeleton-title"></div>
          </div>
          <div class="skeleton-chart-body"></div>
        </div>

        <div class="analytics-chart-card skeleton-chart-card">
          <div class="skeleton-header">
            <div class="skeleton-line skeleton-title"></div>
          </div>
          <div class="skeleton-chart-body"></div>
        </div>

        <div class="analytics-chart-card skeleton-chart-card">
          <div class="skeleton-header">
            <div class="skeleton-line skeleton-title"></div>
          </div>
          <div class="skeleton-chart-body"></div>
        </div>
      </div>
    </div>
  `;
}
