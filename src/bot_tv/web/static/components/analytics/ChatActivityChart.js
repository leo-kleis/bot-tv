import { html, useEffect, useRef, useMemo } from 'preact-setup';
import { Chart } from 'chart.js';
import { CustomSelect } from '/static/components/CustomSelect.js';
import { getChartTheme, getBaseChartOptions } from './chartTheme.js';

const INTERVAL_OPTIONS = [
  { value: '5', label: '5 min' },
  { value: '15', label: '15 min' },
  { value: '30', label: '30 min' },
  { value: '60', label: '60 min' },
];

/**
 * @param {string | null | undefined} isoStr
 * @returns {string}
 */
function formatBucketTime(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    if (Number.isNaN(d.getTime())) return String(isoStr);
    const h = String(d.getHours()).padStart(2, '0');
    const m = String(d.getMinutes()).padStart(2, '0');
    return `${h}:${m}`;
  } catch {
    return String(isoStr);
  }
}

/**
 * @typedef {{
 *   since: string,
 *   until: string,
 *   label: string,
 *   count: number,
 * }} ChatActivityBucketSelection
 */

/**
 * @param {{
 *   data?: Array<Record<string, unknown>> | Record<string, unknown>,
 *   interval?: number,
 *   onIntervalChange?: (interval: number) => void,
 *   onSelectBucket?: (bucket: ChatActivityBucketSelection) => void,
 * }} props
 */
export function ChatActivityChart({ data = [], interval = 5, onIntervalChange, onSelectBucket }) {
  const canvasRef = useRef(/** @type {HTMLCanvasElement | null} */ (null));
  const chartRef = useRef(/** @type {InstanceType<typeof Chart> | null} */ (null));
  const dataRef = useRef(
    /** @type {Array<{ label: string, count: number, uniqueChatters: number, streamMinute: number | null, bucketStartIso: string, bucketEndIso: string, bucketEnd: string }>} */ ([])
  );
  const onSelectBucketRef = useRef(onSelectBucket);
  onSelectBucketRef.current = onSelectBucket;

  const normalizedData = useMemo(() => {
    const rawList = Array.isArray(data)
      ? data
      : (data &&
          /** @type {Array<Record<string, unknown>>} */ (
            data.data || data.activity || data.buckets
          )) ||
        [];

    if (!rawList || rawList.length === 0) return [];

    return rawList.map(item => {
      const bucketStartIso = item.bucket_start ? String(item.bucket_start) : '';
      const parsedStart = bucketStartIso ? Date.parse(bucketStartIso) : Number.NaN;
      const computedEndIso = !Number.isNaN(parsedStart)
        ? new Date(parsedStart + interval * 60000).toISOString()
        : '';
      const bucketEndIso = item.bucket_end ? String(item.bucket_end) : computedEndIso;
      const bucketEnd = bucketEndIso ? formatBucketTime(bucketEndIso) : '';
      const streamMinute = item.stream_minute != null ? Number(item.stream_minute) : null;
      const timeLabel = bucketStartIso
        ? formatBucketTime(bucketStartIso)
        : streamMinute != null
          ? `Min ${streamMinute}`
          : String(item.time || item.bucket || item.timestamp || item.label || '');
      const count =
        item.message_count != null
          ? Number(item.message_count)
          : item.count != null
            ? Number(item.count)
            : Number(item.messages || 0);
      const uniqueChatters = item.unique_chatters != null ? Number(item.unique_chatters) : 0;

      return {
        label: timeLabel,
        count,
        uniqueChatters,
        streamMinute,
        bucketStartIso,
        bucketEndIso: computedEndIso || bucketEndIso,
        bucketEnd,
      };
    });
  }, [data, interval]);

  dataRef.current = normalizedData;

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
    if (!canvas || normalizedData.length === 0) {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
      return;
    }

    const labels = normalizedData.map(d => d.label);
    const counts = normalizedData.map(d => d.count);

    if (chartRef.current) {
      chartRef.current.data.labels = labels;
      chartRef.current.data.datasets[0].data = counts;
      if (chartRef.current.options?.scales?.x?.title) {
        chartRef.current.options.scales.x.title.text = `Intervalo agrupado (${interval} min)`;
      }
      chartRef.current.update('none');
      return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const theme = getChartTheme();

    const options = getBaseChartOptions({
      onHover: (event, elements) => {
        const target = event?.native?.target;
        if (!(target instanceof HTMLElement)) return;
        if (elements && elements.length > 0) {
          const item = dataRef.current[elements[0].index];
          target.style.cursor =
            item && item.count > 0 && item.bucketStartIso ? 'pointer' : 'default';
        } else {
          target.style.cursor = 'default';
        }
      },
      onClick: (_event, elements) => {
        if (!elements || elements.length === 0) return;
        const item = dataRef.current[elements[0].index];
        if (!item || item.count <= 0 || !item.bucketStartIso || !item.bucketEndIso) return;
        if (onSelectBucketRef.current) {
          const rangeLabel = item.bucketEnd ? `${item.label} - ${item.bucketEnd}` : item.label;
          onSelectBucketRef.current({
            since: item.bucketStartIso,
            until: item.bucketEndIso,
            label: rangeLabel,
            count: item.count,
          });
        }
      },
      plugins: {
        tooltip: {
          callbacks: {
            title: function (tooltipItems) {
              if (!tooltipItems.length) return '';
              const index = tooltipItems[0].dataIndex;
              const item = dataRef.current[index];
              if (!item) return '';
              const range = item.bucketEnd ? `${item.label} - ${item.bucketEnd}` : item.label;
              return item.streamMinute != null
                ? `Hora: ${range} (Min ${item.streamMinute})`
                : `Hora: ${range}`;
            },
            label: function (context) {
              const item = dataRef.current[context.dataIndex];
              const base = ` Mensajes: ${context.parsed.y}`;
              if (item && item.uniqueChatters > 0) {
                return `${base} · ${item.uniqueChatters} chatters únicos`;
              }
              return base;
            },
          },
        },
      },
      scales: {
        x: {
          title: {
            display: true,
            text: `Intervalo agrupado (${interval} min)`,
            color: theme.textMuted,
            font: {
              family: theme.fontFamily,
              size: 11,
            },
            padding: { top: 6 },
          },
        },
        y: {
          title: {
            display: true,
            text: 'Mensajes enviados',
            color: theme.textMuted,
            font: {
              family: theme.fontFamily,
              size: 11,
            },
          },
        },
      },
    });

    chartRef.current = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Mensajes',
            data: counts,
            backgroundColor: 'rgba(169, 112, 255, 0.65)',
            hoverBackgroundColor: theme.primary,
            borderColor: theme.primary,
            borderWidth: 1,
            borderRadius: 4,
            maxBarThickness: 32,
          },
        ],
      },
      options,
    });
  }, [normalizedData, interval]);

  return html`
    <div class="analytics-chart-card">
      <div class="analytics-chart-header">
        <div class="analytics-chart-title-wrap">
          <i class="fas fa-comment-dots chart-icon icon-accent" aria-hidden="true"></i>
          <div>
            <h4 class="analytics-chart-title">Actividad del Chat</h4>
            <span class="analytics-chart-subtitle">
              Volumen de mensajes en intervalos de ${interval} min
            </span>
            <span class="analytics-chart-hint">Clic en una barra para ver mensajes</span>
          </div>
        </div>
        ${
          onIntervalChange
            ? html`
                <div class="analytics-chart-control">
                  <${CustomSelect}
                    id="chat-activity-interval"
                    ariaLabel="Intervalo de agrupación del chat"
                    value=${String(interval)}
                    onChange=${val => onIntervalChange(Number(val))}
                    options=${INTERVAL_OPTIONS}
                  />
                </div>
              `
            : null
        }
      </div>
      <div class="analytics-chart-body">
        ${
          normalizedData.length === 0
            ? html`
                <div class="chart-empty-placeholder">
                  <i class="fas fa-comments" aria-hidden="true"></i>
                  <p>Sin actividad registrada en el chat</p>
                </div>
              `
            : html`
                <div class="analytics-chart-container">
                  <canvas ref=${canvasRef}></canvas>
                </div>
              `
        }
      </div>
    </div>
  `;
}
