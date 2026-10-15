import { html } from 'preact-setup';

function formatNumber(val) {
  if (val == null || Number.isNaN(Number(val))) return '—';
  return new Intl.NumberFormat('es-ES').format(Number(val));
}

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

export function AnalyticsSummaryCards({ overview = {}, currentSession = null }) {
  const isLive = currentSession ? Boolean(currentSession.is_live) : Boolean(overview.is_live);
  const duration =
    overview.stream_duration ||
    (currentSession && currentSession.duration) ||
    (currentSession && currentSession.started_at
      ? calculateDuration(currentSession.started_at, currentSession.ended_at)
      : null);

  const peakViewers =
    overview.peak_viewers != null
      ? overview.peak_viewers
      : currentSession && currentSession.peak_viewers != null
        ? currentSession.peak_viewers
        : null;

  const avgViewers =
    overview.avg_viewers != null
      ? overview.avg_viewers
      : currentSession && currentSession.avg_viewers != null
        ? currentSession.avg_viewers
        : null;

  const totalChat =
    overview.total_chat_messages != null
      ? overview.total_chat_messages
      : currentSession && currentSession.total_chat_messages != null
        ? currentSession.total_chat_messages
        : null;

  const msgRate = overview.messages_per_minute || null;

  const totalEvents = overview.total_events != null ? overview.total_events : null;
  const eventsDetail = overview.events_detail || null;

  const netFollowers = overview.net_followers != null ? overview.net_followers : null;
  const newFollowers = overview.new_followers != null ? overview.new_followers : null;
  const lostFollowers = overview.lost_followers != null ? overview.lost_followers : null;

  return html`
    <div class="analytics-summary-grid">
      <!-- 1. Estado / Duración -->
      <div class="analytics-card ${isLive ? 'status-live' : 'status-offline'}">
        <div class="analytics-card-header">
          <span class="analytics-card-label">Estado / Duración</span>
          <div class="analytics-card-icon">
            <i class="fas ${isLive ? 'fa-broadcast-tower' : 'fa-clock'}"></i>
          </div>
        </div>
        <div class="analytics-card-body">
          <div class="analytics-card-value">
            <span class="status-indicator-badge ${isLive ? 'live' : 'offline'}">
              ${isLive ? 'EN VIVO' : 'FINALIZADO'}
            </span>
          </div>
          <div class="analytics-card-subtitle">
            <span>Duración: ${formatDuration(duration)}</span>
          </div>
        </div>
      </div>

      <!-- 2. Pico de espectadores -->
      <div class="analytics-card">
        <div class="analytics-card-header">
          <span class="analytics-card-label">Pico de Espectadores</span>
          <div class="analytics-card-icon icon-primary">
            <i class="fas fa-users"></i>
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
            <i class="fas fa-comments"></i>
          </div>
        </div>
        <div class="analytics-card-body">
          <div class="analytics-card-value">${formatNumber(totalChat)}</div>
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
            <i class="fas fa-bolt"></i>
          </div>
        </div>
        <div class="analytics-card-body">
          <div class="analytics-card-value">${formatNumber(totalEvents)}</div>
          <div class="analytics-card-subtitle">
            ${
              eventsDetail
                ? html`<span>${eventsDetail}</span>`
                : html`<span>Suscripciones, bits y recompensas</span>`
            }
          </div>
        </div>
      </div>

      <!-- 5. Crecimiento neto de seguidores -->
      <div class="analytics-card">
        <div class="analytics-card-header">
          <span class="analytics-card-label">Crecimiento Seguidores</span>
          <div class="analytics-card-icon icon-growth">
            <i class="fas fa-user-plus"></i>
          </div>
        </div>
        <div class="analytics-card-body">
          <div
            class="analytics-card-value ${
              netFollowers > 0 ? 'positive' : netFollowers < 0 ? 'negative' : ''
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
                ? html`
                    <span class="text-success">+${formatNumber(newFollowers || 0)}</span>
                    <span class="divider">·</span>
                    <span class="text-danger">-${formatNumber(lostFollowers || 0)}</span>
                  `
                : html`<span>Balance neto en el período</span>`
            }
          </div>
        </div>
      </div>
    </div>
  `;
}

function calculateDuration(startStr, endStr) {
  try {
    const start = new Date(startStr).getTime();
    const end = endStr ? new Date(endStr).getTime() : Date.now();
    const diffSec = Math.max(0, Math.floor((end - start) / 1000));
    return diffSec;
  } catch {
    return null;
  }
}
