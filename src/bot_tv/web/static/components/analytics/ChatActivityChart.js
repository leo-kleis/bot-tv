import { html, useEffect, useRef, useMemo } from 'preact-setup';
import { Chart } from '/static/vendor/chart.js-auto.esm.js';
import { getChartTheme, getBaseChartOptions } from './chartTheme.js';

export function ChatActivityChart({ data = [], interval = 5 }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  const normalizedData = useMemo(() => {
    const rawList = Array.isArray(data)
      ? data
      : (data && (data.data || data.activity || data.buckets)) || [];

    if (!rawList || rawList.length === 0) return [];

    return rawList.map(item => {
      const timeLabel = item.time || item.bucket || item.timestamp || item.label || '';
      const count = item.count != null ? Number(item.count) : Number(item.messages || 0);
      return {
        label: timeLabel,
        count,
      };
    });
  }, [data]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }

    if (normalizedData.length === 0) return;

    const ctx = canvas.getContext('2d');
    const theme = getChartTheme();

    const labels = normalizedData.map(d => d.label);
    const counts = normalizedData.map(d => d.count);

    const options = getBaseChartOptions({
      plugins: {
        tooltip: {
          callbacks: {
            title: function (tooltipItems) {
              if (!tooltipItems.length) return '';
              const index = tooltipItems[0].dataIndex;
              const item = normalizedData[index];
              return item ? `Hora: ${item.label}` : '';
            },
            label: function (context) {
              return ` Mensajes: ${context.parsed.y}`;
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

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [normalizedData, interval]);

  return html`
    <div class="analytics-chart-card">
      <div class="analytics-chart-header">
        <div class="analytics-chart-title-wrap">
          <i class="fas fa-comment-dots chart-icon icon-accent"></i>
          <div>
            <h4 class="analytics-chart-title">Actividad del Chat</h4>
            <span class="analytics-chart-subtitle">
              Volumen de mensajes en intervalos de ${interval} min
            </span>
          </div>
        </div>
      </div>
      <div class="analytics-chart-body">
        ${
          normalizedData.length === 0
            ? html`
                <div class="chart-empty-placeholder">
                  <i class="fas fa-comments"></i>
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
