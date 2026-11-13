import { html, useMemo } from 'preact-setup';
import { CustomSelect } from '/static/components/CustomSelect.js';

/**
 * @param {string | null | undefined} isoStr
 * @returns {string}
 */
function formatShortDate(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    if (Number.isNaN(d.getTime())) return String(isoStr);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const mins = String(d.getMinutes()).padStart(2, '0');
    return `${day}/${month} ${hours}:${mins}`;
  } catch {
    return String(isoStr);
  }
}

/**
 * @typedef {{
 *   stream_id?: string | number | null,
 *   is_live?: boolean,
 *   started_at?: string | null,
 *   title?: string | null,
 * }} AnalyticsSessionItem
 */

/**
 * @param {{
 *   sessions?: AnalyticsSessionItem[],
 *   selectedSessionId?: string,
 *   onSelectSession: (streamId: string) => void,
 *   onRefresh: () => void,
 *   loading?: boolean,
 * }} props
 */
export function AnalyticsFilterBar({
  sessions = [],
  selectedSessionId = '',
  onSelectSession,
  onRefresh,
  loading = false,
}) {
  const sessionOptions = useMemo(() => {
    if (!sessions || sessions.length === 0) {
      return [{ value: '', label: 'Sin sesiones disponibles' }];
    }
    return sessions
      .filter(s => s && s.stream_id != null && String(s.stream_id).trim() !== '')
      .map(s => {
        const liveTag = s.is_live ? '[EN VIVO] ' : '';
        const date = s.started_at ? formatShortDate(s.started_at) : '';
        const rawTitle = s.title || 'Directo sin título';
        const truncatedTitle = rawTitle.length > 36 ? rawTitle.slice(0, 36) + '...' : rawTitle;
        return {
          value: String(s.stream_id),
          label: `${liveTag}${date} — ${truncatedTitle}`,
        };
      });
  }, [sessions]);

  return html`
    <div class="analytics-filter-bar">
      <!-- Selector de Sesión de Stream -->
      <div class="analytics-filter-item session-filter">
        <label class="analytics-filter-label" for="analytics-session-select">
          <i class="fas fa-video" aria-hidden="true"></i>
          <span>Sesión de Stream</span>
        </label>
        <div class="analytics-select-wrap">
          <${CustomSelect}
            id="analytics-session-select"
            ariaLabel="Seleccionar sesión de stream"
            value=${selectedSessionId || ''}
            onChange=${val => onSelectSession(val || '')}
            options=${sessionOptions}
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
          aria-label="Actualizar datos de analíticas"
        >
          <i class="fas fa-sync-alt ${loading ? 'fa-spin' : ''}" aria-hidden="true"></i>
          <span>Actualizar</span>
        </button>
      </div>
    </div>
  `;
}
