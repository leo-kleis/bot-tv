import { html, useEffect, useRef, useMemo } from 'preact-setup';
import { Chart } from 'chart.js';
import { getChartTheme, createAreaGradient, getBaseChartOptions } from './chartTheme.js';

/**
 * @param {string | null | undefined} isoStr
 * @returns {string}
 */
function formatTimestampTime(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    if (Number.isNaN(d.getTime())) return String(isoStr);
    const h = String(d.getHours()).padStart(2, '0');
    const m = String(d.getMinutes()).padStart(2, '0');
    const s = String(d.getSeconds()).padStart(2, '0');
    return `${h}:${m}:${s}`;
  } catch {
    return String(isoStr);
  }
}

/**
 * @param {{
 *   data?: Array<Record<string, unknown>> | Record<string, unknown>,
 *   session?: Record<string, unknown> | null,
 * }} props
 */
export function ViewersTimelineChart({ data = [], session = null }) {
  const canvasRef = useRef(/** @type {HTMLCanvasElement | null} */ (null));
  const chartRef = useRef(/** @type {InstanceType<typeof Chart> | null} */ (null));
  const dataRef = useRef(
    /** @type {Array<{ minute: number, viewers: number, timeStr: string, label: string }>} */ ([])
  );

  // Normalizar puntos de datos usando recorded_at, stream_minute y viewer_count
  const normalizedData = useMemo(() => {
    const rawList = Array.isArray(data)
      ? data
      : (data &&
          /** @type {Array<Record<string, unknown>>} */ (
            data.timeline || data.data || data.points
          )) ||
        [];

    if (!rawList || rawList.length === 0) return [];

    let startTime = null;
    if (session && session.started_at) {
      startTime = new Date(String(session.started_at)).getTime();
    } else if (rawList[0] && (rawList[0].recorded_at || rawList[0].timestamp)) {
      startTime = new Date(String(rawList[0].recorded_at || rawList[0].timestamp)).getTime();
    }

    return rawList.map((pt, idx) => {
      const rawTimestamp = pt.recorded_at || pt.timestamp || pt.time || pt.created_at;
      const timestamp = rawTimestamp ? String(rawTimestamp) : '';
      let minute =
        pt.stream_minute != null
          ? Number(pt.stream_minute)
          : pt.minute != null
            ? Number(pt.minute)
            : null;
      if (minute == null || Number.isNaN(minute)) {
        if (startTime && timestamp) {
          const ptTime = new Date(timestamp).getTime();
          minute = Math.max(0, Math.round((ptTime - startTime) / 60000));
        } else {
          minute = idx * 5;
        }
      }

      const viewers =
        pt.viewer_count != null
          ? Number(pt.viewer_count)
          : pt.viewers != null
            ? Number(pt.viewers)
            : Number(pt.count || 0);
      const timeStr = timestamp ? formatTimestampTime(timestamp) : '';

      return {
        minute,
        viewers,
        timeStr,
        label: String(minute),
      };
    });
  }, [data, session]);

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
    const values = normalizedData.map(d => d.viewers);

    if (chartRef.current) {
      chartRef.current.data.labels = labels;
      chartRef.current.data.datasets[0].data = values;
      chartRef.current.data.datasets[0].pointRadius = normalizedData.length > 50 ? 0 : 2;
      chartRef.current.update('none');
      return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const theme = getChartTheme();
    const areaGradient = createAreaGradient(
      ctx,
      'rgba(169, 112, 255, 0.35)',
      'rgba(169, 112, 255, 0.01)',
      240
    );

    const options = getBaseChartOptions({
      interaction: {
        mode: 'index',
        axis: 'x',
        intersect: false,
      },
      hover: {
        mode: 'index',
        axis: 'x',
        intersect: false,
      },
      plugins: {
        tooltip: {
          callbacks: {
            title: function (tooltipItems) {
              if (!tooltipItems.length) return '';
              const index = tooltipItems[0].dataIndex;
              const item = dataRef.current[index];
              if (!item) return '';
              const minText = `Minuto ${item.minute}`;
              return item.timeStr ? `${minText} (${item.timeStr})` : minText;
            },
            label: function (context) {
              return ` Espectadores: ${context.parsed.y}`;
            },
          },
        },
      },
      scales: {
        x: {
          title: {
            display: true,
            text: 'Tiempo transcurrido en el directo (min)',
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
            text: 'Espectadores',
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
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Espectadores',
            data: values,
            borderColor: theme.primary,
            borderWidth: 2,
            backgroundColor: areaGradient,
            fill: true,
            tension: 0.3,
            pointRadius: normalizedData.length > 50 ? 0 : 2,
            pointHitRadius: 14,
            pointHoverRadius: 6,
            pointHoverBorderWidth: 2,
            pointBackgroundColor: theme.primary,
            pointBorderColor: '#ffffff',
            pointBorderWidth: 1.5,
          },
        ],
      },
      options,
    });
  }, [normalizedData]);

  return html`
    <div class="analytics-chart-card full-width">
      <div class="analytics-chart-header">
        <div class="analytics-chart-title-wrap">
          <i class="fas fa-chart-area chart-icon icon-primary" aria-hidden="true"></i>
          <div>
            <h4 class="analytics-chart-title">Evolución de Espectadores</h4>
            <span class="analytics-chart-subtitle">
              Línea de tiempo con minuto relativo y hora exacta
            </span>
          </div>
        </div>
      </div>
      <div class="analytics-chart-body">
        ${
          normalizedData.length === 0
            ? html`
                <div class="chart-empty-placeholder">
                  <i class="fas fa-chart-line" aria-hidden="true"></i>
                  <p>Sin registros de espectadores en esta sesión</p>
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
