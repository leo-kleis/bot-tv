import { html } from 'preact-setup';

/**
 * @param {number | string | null | undefined} val
 * @returns {string}
 */
function formatNumber(val) {
  if (val == null || val === '' || Number.isNaN(Number(val))) return '—';
  return new Intl.NumberFormat('es-ES').format(Number(val));
}

/**
 * @param {number | string | null | undefined} secondsOrStr
 * @returns {string}
 */
function formatDuration(secondsOrStr) {
  if (secondsOrStr == null || secondsOrStr === '') return '—';
  if (typeof secondsOrStr === 'string' && secondsOrStr.includes(':')) {
    return secondsOrStr;
  }
  const sec = Number(secondsOrStr);
  if (Number.isNaN(sec) || sec <= 0) return '—';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) {
    return `${h}h ${m}m ${s}s`;
  }
  return `${m}m ${s}s`;
}

/**
 * @param {string | null | undefined} startedAt
 * @param {string | null | undefined} endedAt
 * @returns {number | null}
 */
function calculateDurationSeconds(startedAt, endedAt) {
  if (!startedAt) return null;
  const startMs = new Date(startedAt).getTime();
  const endMs = endedAt ? new Date(endedAt).getTime() : Date.now();
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs <= startMs) return null;
  return Math.floor((endMs - startMs) / 1000);
}

/**
 * @param {{
 *   overview?: Record<string, unknown>,
 *   currentSession?: Record<string, unknown> | null,
 *   onOpenFollowersDetail?: () => void,
 *   canOpenFollowersDetail?: boolean,
 * }} props
 */
export function AnalyticsSummaryCards({
  overview = {},
  currentSession = null,
  onOpenFollowersDetail,
  canOpenFollowersDetail = false,
}) {
  const isLive =
    overview.is_live != null
      ? Boolean(overview.is_live)
      : currentSession
        ? Boolean(currentSession.is_live)
        : false;

  const durationSeconds =
    overview.duration_seconds != null && Number(overview.duration_seconds) > 0
      ? Number(overview.duration_seconds)
      : currentSession && currentSession.started_at
        ? calculateDurationSeconds(
            String(currentSession.started_at),
            currentSession.ended_at ? String(currentSession.ended_at) : null
          )
        : null;

  const peakViewers =
    overview.peak_viewers != null
      ? Number(overview.peak_viewers)
      : currentSession && currentSession.peak_viewers != null
        ? Number(currentSession.peak_viewers)
        : null;

  const avgViewers = overview.avg_viewers != null ? Number(overview.avg_viewers) : null;

  const totalMessages = overview.total_messages != null ? Number(overview.total_messages) : null;
  const msgRate =
    overview.messages_per_minute != null ? Number(overview.messages_per_minute) : null;

  const totalEvents = overview.total_events != null ? Number(overview.total_events) : null;
  const eventsDetail = typeof overview.events_detail === 'string' ? overview.events_detail : '';

  const netFollowers = overview.net_followers != null ? Number(overview.net_followers) : null;
  const newFollowers = overview.new_followers != null ? Number(overview.new_followers) : null;
  const lostFollowers = overview.lost_followers != null ? Number(overview.lost_followers) : null;

  return html`
    <div class="analytics-summary-grid">
      <!-- 1. Estado / Duración -->
      <div class="analytics-card ${isLive ? 'status-live' : 'status-offline'}">
        <div class="analytics-card-header">
          <span class="analytics-card-label">Estado / Duración</span>
          <div class="analytics-card-icon">
            <i class="fas ${isLive ? 'fa-broadcast-tower' : 'fa-clock'}" aria-hidden="true"></i>
          </div>
        </div>
        <div class="analytics-card-body">
          <div class="analytics-card-value">
            <span class="status-indicator-badge ${isLive ? 'live' : 'offline'}">
              ${isLive ? 'EN VIVO' : 'FINALIZADO'}
            </span>
          </div>
          <div class="analytics-card-subtitle">
            <span>Duración: ${formatDuration(durationSeconds)}</span>
          </div>
        </div>
      </div>

      <!-- 2. Pico de espectadores -->
      <div class="analytics-card">
        <div class="analytics-card-header">
          <span class="analytics-card-label">Pico de Espectadores</span>
          <div class="analytics-card-icon icon-primary">
            <i class="fas fa-users" aria-hidden="true"></i>
          </div>
        </div>
        <div class="analytics-card-body">
          <div class="analytics-card-value">${formatNumber(peakViewers)}</div>
          <div class="analytics-card-subtitle">
            ${
              avgViewers != null
                ? html`<span>Promedio: <strong>${formatNumber(avgViewers)}</strong></span>`
                : html`<span>Espectadores máximos en simultáneo</span>`
            }
          </div>
        </div>
      </div>

      <!-- 3. Volumen de chat -->
      <div class="analytics-card">
        <div class="analytics-card-header">
          <span class="analytics-card-label">Volumen de Chat</span>
          <div class="analytics-card-icon icon-accent">
            <i class="fas fa-comments" aria-hidden="true"></i>
          </div>
        </div>
        <div class="analytics-card-body">
          <div class="analytics-card-value">${formatNumber(totalMessages)}</div>
          <div class="analytics-card-subtitle">
            ${
              msgRate != null
                ? html`<span>Ritmo: <strong>${msgRate}</strong> msgs/min</span>`
                : html`<span>Mensajes totales registrados</span>`
            }
          </div>
        </div>
      </div>

      <!-- 4. Eventos del directo -->
      <div class="analytics-card">
        <div class="analytics-card-header">
          <span class="analytics-card-label">Eventos del Directo</span>
          <div class="analytics-card-icon icon-events">
            <i class="fas fa-bolt" aria-hidden="true"></i>
          </div>
        </div>
        <div class="analytics-card-body">
          <div class="analytics-card-value">${formatNumber(totalEvents)}</div>
          <div class="analytics-card-subtitle">
            ${
              eventsDetail
                ? html`<span>${eventsDetail}</span>`
                : html`<span>Subs, bits, raids y canjes</span>`
            }
          </div>
        </div>
      </div>

      <!-- 5. Balance de seguidores -->
      <button
        type="button"
        class="analytics-card analytics-card-interactive"
        onClick=${onOpenFollowersDetail}
        disabled=${!canOpenFollowersDetail}
      >
        <div class="analytics-card-header">
          <span class="analytics-card-label">Balance de Seguidores</span>
          <div
            class="analytics-card-icon ${
              netFollowers != null && netFollowers < 0 ? 'icon-danger' : 'icon-growth'
            }"
          >
            <i class="fas fa-user-plus" aria-hidden="true"></i>
          </div>
        </div>
        <div class="analytics-card-body">
          <div
            class="analytics-card-value ${
              netFollowers != null
                ? netFollowers > 0
                  ? 'positive'
                  : netFollowers < 0
                    ? 'negative'
                    : ''
                : ''
            }"
          >
            ${
              netFollowers != null
                ? `${netFollowers > 0 ? '+' : ''}${formatNumber(netFollowers)}`
                : '—'
            }
          </div>
          <div class="analytics-card-subtitle">
            ${
              newFollowers != null || lostFollowers != null
                ? html`<span
                    >+${formatNumber(newFollowers || 0)} nuevos /
                    -${formatNumber(lostFollowers || 0)} perdidos</span
                  >`
                : html`<span>Crecimiento neto del período</span>`
            }
            ${
              canOpenFollowersDetail
                ? html`<span class="analytics-card-action-hint">
                    Ver usuarios <i class="fas fa-chevron-right" aria-hidden="true"></i>
                  </span>`
                : null
            }
          </div>
        </div>
      </button>
    </div>
  `;
}
