import { html, useMemo } from 'preact-setup';
import { CustomSelect } from '/static/components/CustomSelect.js';

function formatShortDate(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const mins = String(d.getMinutes()).padStart(2, '0');
    return `${day}/${month} ${hours}:${mins}`;
  } catch {
    return isoStr;
  }
}

export function AnalyticsFilterBar({
  sessions = [],
  selectedSessionId,
  onSelectSession,
  chatInterval = 5,
  onChangeChatInterval,
  period = '24h',
  onChangePeriod,
  onRefresh,
  loading = false,
}) {
  const sessionOptions = useMemo(() => {
    if (!sessions || sessions.length === 0) {
      return [{ value: '', label: 'Sin sesiones disponibles' }];
    }
    return sessions.map(s => {
      const liveTag = s.is_live ? '[EN VIVO] ' : '';
      const date = s.started_at ? formatShortDate(s.started_at) : '';
      const rawTitle = s.title || 'Directo sin título';
      const truncatedTitle = rawTitle.length > 36 ? rawTitle.slice(0, 36) + '...' : rawTitle;
      return {
        value: String(s.id),
        label: `${liveTag}${date} — ${truncatedTitle}`,
      };
    });
  }, [sessions]);

  const intervalOptions = useMemo(
    () => [
      { value: 1, label: '1 minuto' },
      { value: 5, label: '5 minutos' },
      { value: 15, label: '15 minutos' },
      { value: 30, label: '30 minutos' },
      { value: 60, label: '60 minutos' },
    ],
    []
  );

  const periodOptions = useMemo(
    () => [
      { value: '24h', label: 'Últimas 24h' },
      { value: '7d', label: 'Últimos 7 días' },
      { value: '30d', label: 'Últimos 30 días' },
      { value: 'all', label: 'Todo el historial' },
    ],
    []
  );

  return html`
    <div class="analytics-filter-bar">
      <!-- Selector de Sesión de Stream -->
      <div class="analytics-filter-item session-filter">
        <label class="analytics-filter-label">
          <i class="fas fa-video"></i>
          <span>Sesión de Stream</span>
        </label>
        <div class="analytics-select-wrap">
          <${CustomSelect}
            value=${selectedSessionId != null ? String(selectedSessionId) : ''}
            onChange=${val => onSelectSession(val ? Number(val) : null)}
            options=${sessionOptions}
          />
        </div>
      </div>

      <!-- Selector de Granularidad de Chat -->
      <div class="analytics-filter-item interval-filter">
        <label class="analytics-filter-label">
          <i class="fas fa-chart-bar"></i>
          <span>Intervalo Chat</span>
        </label>
        <div class="analytics-select-wrap">
          <${CustomSelect}
            value=${chatInterval}
            onChange=${val => onChangeChatInterval(Number(val))}
            options=${intervalOptions}
          />
        </div>
      </div>

      <!-- Selector de Período -->
      <div class="analytics-filter-item period-filter">
        <label class="analytics-filter-label">
          <i class="fas fa-calendar-alt"></i>
          <span>Período General</span>
        </label>
        <div class="analytics-select-wrap">
          <${CustomSelect}
            value=${period}
            onChange=${val => onChangePeriod(val)}
            options=${periodOptions}
          />
        </div>
      </div>

      <!-- Acciones de Barra / Refresco -->
      <div class="analytics-filter-actions">
        <button
          type="button"
          class="analytics-refresh-btn"
          onClick=${onRefresh}
          disabled=${loading}
          title="Actualizar datos de analíticas"
        >
          <i class="fas fa-sync-alt ${loading ? 'fa-spin' : ''}"></i>
          <span class="btn-text">Actualizar</span>
        </button>
      </div>
    </div>
  `;
}
