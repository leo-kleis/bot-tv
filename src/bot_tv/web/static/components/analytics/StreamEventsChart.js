import { html, useState, useEffect, useRef, useMemo, useCallback } from 'preact-setup';
import { Chart } from 'chart.js';
import { getChartTheme, getBaseChartOptions, formatShortDateTime } from './chartTheme.js';

const REWARD_PALETTE = [
  '#38bdf8',
  '#2dd4bf',
  '#60a5fa',
  '#818cf8',
  '#f472b6',
  '#fb923c',
  '#34d399',
  '#a78bfa',
];

/** @type {Record<string, string>} */
const EVENT_LABELS = {
  subscription_gift: 'Regalos de Sub',
  subscription_message: 'Resubs',
  subscription: 'Suscripciones',
  cheer: 'Bits / Cheers',
  raid: 'Raids',
  prediction: 'Predicciones',
  follow: 'Seguidores',
};

/**
 * @param {Record<string, unknown>} ev
 * @returns {string}
 */
function extractTimelineUser(ev) {
  const ed = ev.event_data;
  if (!ed || typeof ed !== 'object') return '';
  const dataObj = /** @type {Record<string, unknown>} */ (ed);
  const raw =
    dataObj.display_name ||
    dataObj.from_display_name ||
    dataObj.user_name ||
    dataObj.from_broadcaster ||
    dataObj.user_login ||
    dataObj.username ||
    dataObj.from_broadcaster_user_name ||
    (dataObj.anonymous ? 'Anónimo' : '');
  return raw ? String(raw) : '';
}

/**
 * @param {unknown} rawTier
 * @returns {string}
 */
function formatSubTier(rawTier) {
  if (!rawTier) return '';
  const s = String(rawTier).trim();
  if (s === '1000' || s === '1') return 'Tier 1';
  if (s === '2000' || s === '2') return 'Tier 2';
  if (s === '3000' || s === '3') return 'Tier 3';
  if (s.toLowerCase().includes('prime')) return 'Prime';
  return s;
}

/**
 * @param {string} eventType
 * @returns {string}
 */
function formatMetricUnit(eventType) {
  if (eventType === 'cheer') return 'bits';
  if (eventType === 'raid') return 'espectadores';
  return 'pts';
}

/**
 * @param {Record<string, unknown>} ev
 * @param {string} eventType
 * @returns {string}
 */
function extractTimelineDetail(ev, eventType) {
  const ed = ev.event_data;
  if (!ed || typeof ed !== 'object') return '';
  const dataObj = /** @type {Record<string, unknown>} */ (ed);
  if (eventType === 'cheer') {
    const bits = Number(dataObj.bits ?? ev.metric_value ?? 0);
    return bits > 0 ? `${bits.toLocaleString('es-ES')} bits` : '';
  }
  if (eventType === 'raid') {
    const viewers = Number(dataObj.viewer_count ?? dataObj.viewers ?? ev.metric_value ?? 0);
    return viewers > 0 ? `${viewers.toLocaleString('es-ES')} espectadores` : '';
  }
  if (eventType === 'channel_points') {
    const cost = Number(dataObj.reward_cost ?? dataObj.cost ?? ev.metric_value ?? 0);
    return cost > 0 ? `${cost.toLocaleString('es-ES')} pts` : '';
  }
  if (eventType === 'subscription_gift') {
    const total = Number(dataObj.total ?? dataObj.gift_count ?? ev.metric_value ?? 0);
    const tier = formatSubTier(dataObj.tier);
    const parts = [];
    if (total > 0) parts.push(`${total} ${total === 1 ? 'sub regalada' : 'subs regaladas'}`);
    if (tier) parts.push(tier);
    return parts.join(' · ');
  }
  if (eventType === 'subscription' || eventType === 'subscription_message') {
    const tier = formatSubTier(dataObj.tier);
    const months = Number(dataObj.cumulative_months ?? dataObj.streak_months ?? 0);
    const parts = [];
    if (tier) parts.push(tier);
    if (months > 0) parts.push(`${months} ${months === 1 ? 'mes' : 'meses'}`);
    return parts.join(' · ');
  }
  return '';
}

/**
 * @param {Record<string, unknown>} ev
 * @param {Record<string, unknown> | null} session
 * @returns {{ timestamp: string, momentText: string }}
 */
function resolveEventMoment(ev, session) {
  const timestamp = ev.timestamp ? String(ev.timestamp) : '';
  /** @type {number | null} */
  let minute = null;
  if (
    ev.stream_minute != null &&
    ev.stream_minute !== '' &&
    Number.isFinite(Number(ev.stream_minute))
  ) {
    minute = Math.max(0, Math.floor(Number(ev.stream_minute)));
  } else if (timestamp && session && session.started_at) {
    const evTs = new Date(timestamp).getTime();
    const startTs = new Date(String(session.started_at)).getTime();
    if (Number.isFinite(evTs) && Number.isFinite(startTs)) {
      minute = Math.max(0, Math.floor((evTs - startTs) / 60000));
    }
  }

  const formattedDate = timestamp ? formatShortDateTime(timestamp) : '—';
  const hasDate = formattedDate !== '—';
  const hasMin = minute !== null;

  let momentText = '';
  if (hasDate && hasMin) {
    momentText = `${formattedDate} · Min ${minute}`;
  } else if (hasDate) {
    momentText = formattedDate;
  } else if (hasMin) {
    momentText = `Min ${minute}`;
  }

  return { timestamp, momentText };
}

/**
 * @param {Record<string, unknown>} ev
 * @returns {string | null}
 */
function extractTimelineRewardTitle(ev) {
  const ed = ev.event_data;
  if (!ed || typeof ed !== 'object') return null;
  const dataObj = /** @type {Record<string, unknown>} */ (ed);
  const title = dataObj.reward_title ? String(dataObj.reward_title).trim() : '';
  return title || 'Recompensa';
}

/**
 * @typedef {{
 *   key: string,
 *   eventType: string,
 *   rewardTitle: string | null,
 *   label: string,
 *   color: string,
 *   count: number,
 *   metricTotal: number,
 *   recentUsers: string[],
 *   lastMoment: string,
 * }} EventSegment
 */

/**
 * @typedef {{
 *   id: string,
 *   color: string,
 *   label: string,
 *   user: string,
 *   detailText: string,
 *   timestamp: string,
 *   momentText: string,
 * }} TimelineEventItem
 */

/**
 * @param {{
 *   data?: Record<string, unknown> | Array<Record<string, unknown>> | null,
 *   session?: Record<string, unknown> | null,
 * }} props
 */
export function StreamEventsChart({ data = null, session = null }) {
  const canvasRef = useRef(/** @type {HTMLCanvasElement | null} */ (null));
  const chartRef = useRef(/** @type {InstanceType<typeof Chart> | null} */ (null));
  const segmentsRef = useRef(/** @type {EventSegment[]} */ ([]));
  const [activeTab, setActiveTab] = useState(/** @type {'timeline' | 'summary'} */ ('timeline'));
  const tabRefs = useRef(/** @type {Record<string, HTMLButtonElement | null>} */ ({}));

  const eventSegments = useMemo(() => {
    if (!data) return /** @type {EventSegment[]} */ ([]);
    const theme = getChartTheme();

    /** @type {Record<string, string>} */
    const semanticColors = {
      subscription_gift: theme.alertGiftSub,
      subscription_message: theme.accent,
      subscription: theme.alertSub,
      cheer: theme.alertCheer,
      raid: theme.alertRaid,
      prediction: theme.alertPrediction,
      follow: theme.online,
    };

    const rawSummary = Array.isArray(data) ? data : data.summary || data.events || data.data || [];
    const timeline = !Array.isArray(data) && Array.isArray(data.timeline) ? data.timeline : [];

    if (!Array.isArray(rawSummary) || rawSummary.length === 0) {
      return /** @type {EventSegment[]} */ ([]);
    }

    let rewardIdx = 0;
    /** @type {EventSegment[]} */
    const segments = [];

    for (const item of rawSummary) {
      const eventType = String(item.event_type || item.type || '').toLowerCase();
      const count = Number(
        item.event_count != null ? item.event_count : item.count != null ? item.count : 0
      );
      if (!eventType || count <= 0) continue;

      const rewardTitle =
        eventType === 'channel_points' ? String(item.reward_title || 'Canje de Puntos') : null;
      const metricTotal = item.total_metric_value != null ? Number(item.total_metric_value) : 0;

      const label =
        eventType === 'channel_points'
          ? rewardTitle || 'Canje de Puntos'
          : EVENT_LABELS[eventType] || eventType;

      let color = semanticColors[eventType];
      if (!color) {
        color = REWARD_PALETTE[rewardIdx % REWARD_PALETTE.length];
        rewardIdx += 1;
      }

      // Extraer hasta 3 usuarios más recientes coincidentes y el último momento desde timeline (orden inverso)
      /** @type {string[]} */
      const recentUsers = [];
      let lastMoment = '';
      for (let i = timeline.length - 1; i >= 0; i--) {
        const ev = /** @type {Record<string, unknown>} */ (timeline[i]);
        const evType = String(ev.event_type || '').toLowerCase();
        if (evType !== eventType) continue;
        if (eventType === 'channel_points') {
          const evReward = extractTimelineRewardTitle(ev);
          if (evReward !== rewardTitle) continue;
        }
        if (!lastMoment) {
          lastMoment = resolveEventMoment(ev, session).momentText;
        }
        const uname = extractTimelineUser(ev);
        if (uname && !recentUsers.includes(uname) && recentUsers.length < 3) {
          recentUsers.push(uname);
        }
        if (lastMoment && recentUsers.length >= 3) break;
      }

      segments.push({
        key: `${eventType}:${rewardTitle || ''}`,
        eventType,
        rewardTitle,
        label,
        color,
        count,
        metricTotal,
        recentUsers,
        lastMoment,
      });
    }

    return segments;
  }, [data, session]);

  const timelineEvents = useMemo(() => {
    if (!data || Array.isArray(data) || !Array.isArray(data.timeline)) {
      return /** @type {TimelineEventItem[]} */ ([]);
    }
    const theme = getChartTheme();
    /** @type {Map<string, string>} */
    const segmentColorMap = new Map();
    for (const seg of eventSegments) {
      segmentColorMap.set(seg.key, seg.color);
    }

    return data.timeline.map((rawEv, idx) => {
      const ev = /** @type {Record<string, unknown>} */ (rawEv);
      const evType = String(ev.event_type || ev.type || '').toLowerCase();
      const rewardTitle = evType === 'channel_points' ? extractTimelineRewardTitle(ev) : null;
      const key = `${evType}:${rewardTitle || ''}`;
      const color = segmentColorMap.get(key) || theme.accent;
      const label =
        evType === 'channel_points'
          ? rewardTitle || 'Canje de Puntos'
          : EVENT_LABELS[evType] || evType;
      const user = extractTimelineUser(ev);
      const detailText = extractTimelineDetail(ev, evType);
      const { timestamp, momentText } = resolveEventMoment(ev, session);
      const id = ev.id != null ? String(ev.id) : `${evType || 'event'}-${idx}`;
      return {
        id,
        color,
        label,
        user,
        detailText,
        timestamp,
        momentText,
      };
    });
  }, [data, session, eventSegments]);

  segmentsRef.current = eventSegments;

  const handleTabKeyDown = useCallback(
    /** @param {KeyboardEvent} e */
    e => {
      const order = /** @type {const} */ (['timeline', 'summary']);
      const currentIdx = order.indexOf(activeTab);
      let nextIdx = -1;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        nextIdx = (currentIdx + 1) % order.length;
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        nextIdx = (currentIdx - 1 + order.length) % order.length;
      } else if (e.key === 'Home') {
        nextIdx = 0;
      } else if (e.key === 'End') {
        nextIdx = order.length - 1;
      }
      if (nextIdx !== -1) {
        e.preventDefault();
        const nextTab = order[nextIdx];
        setActiveTab(nextTab);
        tabRefs.current[nextTab]?.focus();
      }
    },
    [activeTab]
  );

  const totalEvents = useMemo(() => {
    return eventSegments.reduce((acc, curr) => acc + curr.count, 0);
  }, [eventSegments]);

  useEffect(() => {
    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || eventSegments.length === 0) {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
      return;
    }

    const labels = eventSegments.map(s => s.label);
    const counts = eventSegments.map(s => s.count);
    const bgColors = eventSegments.map(s => s.color);

    if (chartRef.current) {
      chartRef.current.data.labels = labels;
      chartRef.current.data.datasets[0].data = counts;
      chartRef.current.data.datasets[0].backgroundColor = bgColors;
      chartRef.current.update('none');
      return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const theme = getChartTheme();

    const options = getBaseChartOptions({
      cutout: '70%',
      plugins: {
        legend: {
          display: true,
          position: 'bottom',
          labels: {
            color: theme.textMain,
            font: {
              family: theme.fontFamily,
              size: 11,
            },
            padding: 12,
            usePointStyle: true,
            pointStyle: 'circle',
          },
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              const seg = segmentsRef.current[context.dataIndex];
              const val = context.parsed;
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0';
              const lines = [` ${context.label}: ${val} (${pct}%)`];
              if (seg && seg.metricTotal > 0) {
                lines.push(
                  ` Total: ${seg.metricTotal.toLocaleString('es-ES')} ${formatMetricUnit(seg.eventType)}`
                );
              }
              if (seg && seg.recentUsers.length > 0) {
                lines.push(` Recientes: ${seg.recentUsers.join(', ')}`);
              }
              return lines;
            },
          },
        },
      },
      scales: {
        x: { display: false },
        y: { display: false },
      },
    });

    chartRef.current = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [
          {
            data: counts,
            backgroundColor: bgColors,
            borderColor: theme.bgCard,
            borderWidth: 2,
            hoverOffset: 6,
          },
        ],
      },
      options,
    });
  }, [eventSegments]);

  return html`
    <div class="analytics-chart-card full-width analytics-events-chart-card">
      <div class="analytics-chart-header">
        <div class="analytics-chart-title-wrap">
          <i class="fas fa-bolt chart-icon icon-events" aria-hidden="true"></i>
          <div>
            <h4 class="analytics-chart-title">Eventos del Directo</h4>
            <span class="analytics-chart-subtitle">
              ${totalEvents > 0 ? `${totalEvents} eventos registrados` : 'Distribución por tipo'}
            </span>
          </div>
        </div>
      </div>
      <div class="analytics-chart-body analytics-events-body">
        ${
          eventSegments.length === 0
            ? html`
                <div class="chart-empty-placeholder">
                  <i class="fas fa-star" aria-hidden="true"></i>
                  <p>Sin eventos especiales en esta sesión</p>
                </div>
              `
            : html`
                <div class="analytics-events-visual">
                  <div class="analytics-chart-container doughnut-container">
                    <canvas ref=${canvasRef}></canvas>
                  </div>
                </div>
                <div class="analytics-events-breakdown">
                  <div
                    class="analytics-events-tabs"
                    role="tablist"
                    aria-label="Vista de eventos del directo"
                  >
                    <button
                      type="button"
                      role="tab"
                      id="events-tab-timeline"
                      class="analytics-events-tab-btn${activeTab === 'timeline' ? ' active' : ''}"
                      aria-selected=${activeTab === 'timeline'}
                      aria-controls="events-tabpanel-timeline"
                      tabindex=${activeTab === 'timeline' ? 0 : -1}
                      ref=${el => {
                        tabRefs.current.timeline = el;
                      }}
                      onClick=${() => setActiveTab('timeline')}
                      onKeyDown=${handleTabKeyDown}
                    >
                      Cronología (${timelineEvents.length})
                    </button>
                    <button
                      type="button"
                      role="tab"
                      id="events-tab-summary"
                      class="analytics-events-tab-btn${activeTab === 'summary' ? ' active' : ''}"
                      aria-selected=${activeTab === 'summary'}
                      aria-controls="events-tabpanel-summary"
                      tabindex=${activeTab === 'summary' ? 0 : -1}
                      ref=${el => {
                        tabRefs.current.summary = el;
                      }}
                      onClick=${() => setActiveTab('summary')}
                      onKeyDown=${handleTabKeyDown}
                    >
                      Por tipo (${eventSegments.length})
                    </button>
                  </div>

                  <div
                    role="tabpanel"
                    id="events-tabpanel-${activeTab}"
                    aria-labelledby="events-tab-${activeTab}"
                  >
                    ${
                      activeTab === 'timeline'
                        ? timelineEvents.length === 0
                          ? html`
                              <p class="analytics-events-empty-tab">
                                Sin marcas temporales registradas para esta sesión
                              </p>
                            `
                          : html`
                              <ul class="analytics-events-breakdown-list">
                                ${timelineEvents.map(ev => {
                                  const subText = [ev.user, ev.detailText]
                                    .filter(Boolean)
                                    .join(' · ');
                                  return html`
                                    <li class="analytics-events-breakdown-item" key=${ev.id}>
                                      <span
                                        class="analytics-events-dot"
                                        style="background-color: ${ev.color};"
                                        aria-hidden="true"
                                      ></span>
                                      <div class="analytics-events-info">
                                        <span class="analytics-events-name">${ev.label}</span>
                                        ${
                                          subText
                                            ? html`<span class="analytics-events-users">
                                                ${subText}
                                              </span>`
                                            : null
                                        }
                                      </div>
                                      ${
                                        ev.momentText
                                          ? html`
                                              <div
                                                class="analytics-events-meta analytics-events-meta-timeline"
                                              >
                                                <time
                                                  class="analytics-events-time"
                                                  datetime=${ev.timestamp || undefined}
                                                >
                                                  ${ev.momentText}
                                                </time>
                                              </div>
                                            `
                                          : null
                                      }
                                    </li>
                                  `;
                                })}
                              </ul>
                            `
                        : html`
                            <ul class="analytics-events-breakdown-list">
                              ${eventSegments.map(seg => {
                                const metricLabel =
                                  seg.metricTotal > 0
                                    ? `${seg.metricTotal.toLocaleString('es-ES')} ${formatMetricUnit(seg.eventType)}`
                                    : '';
                                return html`
                                  <li class="analytics-events-breakdown-item" key=${seg.key}>
                                    <span
                                      class="analytics-events-dot"
                                      style="background-color: ${seg.color};"
                                      aria-hidden="true"
                                    ></span>
                                    <div class="analytics-events-info">
                                      <span class="analytics-events-name">${seg.label}</span>
                                      ${
                                        seg.recentUsers.length > 0
                                          ? html`<span class="analytics-events-users">
                                              ${seg.recentUsers.join(', ')}
                                            </span>`
                                          : null
                                      }
                                      ${
                                        seg.lastMoment
                                          ? html`<span class="analytics-events-time">
                                              Último: ${seg.lastMoment}
                                            </span>`
                                          : null
                                      }
                                    </div>
                                    <div class="analytics-events-meta">
                                      <span class="analytics-events-count">${seg.count}</span>
                                      ${
                                        metricLabel
                                          ? html`<span class="analytics-events-users"
                                              >${metricLabel}</span
                                            >`
                                          : null
                                      }
                                    </div>
                                  </li>
                                `;
                              })}
                            </ul>
                          `
                    }
                  </div>
                </div>
              `
        }
      </div>
    </div>
  `;
}
