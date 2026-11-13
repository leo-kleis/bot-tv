import { html, useEffect, useRef, useMemo } from 'preact-setup';
import { Chart } from 'chart.js';
import { getChartTheme, getBaseChartOptions } from './chartTheme.js';

/**
 * @typedef {{
 *   userId: string,
 *   username: string,
 *   displayName: string,
 *   count: number,
 * }} TopChatterSelection
 */

/**
 * @param {{
 *   data?: Array<Record<string, unknown>> | Record<string, unknown>,
 *   onSelectChatter?: (chatter: TopChatterSelection) => void,
 * }} props
 */
export function TopChattersChart({ data = [], onSelectChatter }) {
  const canvasRef = useRef(/** @type {HTMLCanvasElement | null} */ (null));
  const chartRef = useRef(/** @type {InstanceType<typeof Chart> | null} */ (null));
  const dataRef = useRef(
    /** @type {Array<{ userId: string, username: string, displayName: string, count: number }>} */ ([])
  );
  const onSelectChatterRef = useRef(onSelectChatter);
  onSelectChatterRef.current = onSelectChatter;

  const normalizedData = useMemo(() => {
    const rawList = Array.isArray(data)
      ? data
      : (data &&
          /** @type {Array<Record<string, unknown>>} */ (
            data.chatters || data.data || data.top_users
          )) ||
        [];

    if (!rawList || rawList.length === 0) return [];

    return rawList
      .slice(0, 10)
      .map(item => {
        const userId = String(item.user_id || '');
        const username = String(item.username || item.user || item.name || 'Desconocido');
        const displayName = String(
          item.nickname ||
            item.display_name ||
            item.username ||
            item.user ||
            item.name ||
            'Desconocido'
        );
        const count =
          item.msg_count != null
            ? Number(item.msg_count)
            : item.message_count != null
              ? Number(item.message_count)
              : Number(item.count || item.messages || 0);
        return { userId, username, displayName, count };
      })
      .sort((a, b) => b.count - a.count);
  }, [data]);

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

    const labels = normalizedData.map(d => d.displayName);
    const counts = normalizedData.map(d => d.count);

    if (chartRef.current) {
      chartRef.current.data.labels = labels;
      chartRef.current.data.datasets[0].data = counts;
      chartRef.current.update('none');
      return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const theme = getChartTheme();

    const options = getBaseChartOptions({
      indexAxis: 'y',
      onHover: (event, elements) => {
        const target = event?.native?.target;
        if (!(target instanceof HTMLElement)) return;
        if (elements && elements.length > 0) {
          const item = dataRef.current[elements[0].index];
          target.style.cursor = item && item.userId ? 'pointer' : 'default';
        } else {
          target.style.cursor = 'default';
        }
      },
      onClick: (_event, elements) => {
        if (!elements || elements.length === 0) return;
        const item = dataRef.current[elements[0].index];
        if (!item || !item.userId) return;
        if (onSelectChatterRef.current) {
          onSelectChatterRef.current(item);
        }
      },
      plugins: {
        tooltip: {
          callbacks: {
            title: function (tooltipItems) {
              if (!tooltipItems.length) return '';
              const index = tooltipItems[0].dataIndex;
              const item = dataRef.current[index];
              return item ? `Usuario: ${item.displayName}` : '';
            },
            label: function (context) {
              return ` Mensajes enviados: ${context.parsed.x}`;
            },
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          title: {
            display: true,
            text: 'Cantidad de mensajes',
            color: theme.textMuted,
            font: {
              family: theme.fontFamily,
              size: 11,
            },
            padding: { top: 6 },
          },
          grid: {
            color: 'rgba(255, 255, 255, 0.04)',
            drawBorder: false,
          },
          ticks: {
            color: theme.textMuted,
            font: {
              family: theme.fontFamily,
              size: 11,
            },
            precision: 0,
          },
          border: {
            display: false,
          },
        },
        y: {
          grid: {
            display: false,
            drawBorder: false,
          },
          ticks: {
            color: theme.textMain,
            font: {
              family: theme.fontFamily,
              size: 11,
              weight: '500',
            },
          },
          border: {
            display: false,
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
            backgroundColor: 'rgba(140, 78, 235, 0.75)',
            hoverBackgroundColor: theme.primary,
            borderColor: theme.accent,
            borderWidth: 1,
            borderRadius: 4,
            maxBarThickness: 20,
          },
        ],
      },
      options,
    });
  }, [normalizedData]);

  return html`
    <div class="analytics-chart-card">
      <div class="analytics-chart-header">
        <div class="analytics-chart-title-wrap">
          <i class="fas fa-trophy chart-icon icon-gold" aria-hidden="true"></i>
          <div>
            <h4 class="analytics-chart-title">Top 10 Chatters</h4>
            <span class="analytics-chart-subtitle">
              Usuarios más participativos de la sesión seleccionada
            </span>
            <span class="analytics-chart-hint">Clic en una barra para ver mensajes</span>
          </div>
        </div>
      </div>
      <div class="analytics-chart-body">
        ${
          normalizedData.length === 0
            ? html`
                <div class="chart-empty-placeholder">
                  <i class="fas fa-user-friends" aria-hidden="true"></i>
                  <p>Sin datos de participación en esta sesión</p>
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
