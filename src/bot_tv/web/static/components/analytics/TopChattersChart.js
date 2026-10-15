import { html, useEffect, useRef, useMemo } from 'preact-setup';
import { Chart } from '/static/vendor/chart.js-auto.esm.js';
import { getChartTheme, getBaseChartOptions } from './chartTheme.js';

export function TopChattersChart({ data = [], period = '24h' }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  const normalizedData = useMemo(() => {
    const rawList = Array.isArray(data)
      ? data
      : (data && (data.chatters || data.data || data.top_users)) || [];

    if (!rawList || rawList.length === 0) return [];

    return rawList
      .slice(0, 10)
      .map(item => {
        const username = item.username || item.user || item.name || 'Desconocido';
        const count =
          item.message_count != null
            ? Number(item.message_count)
            : Number(item.count || item.messages || 0);
        return { username, count };
      })
      .sort((a, b) => b.count - a.count);
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

    const labels = normalizedData.map(d => d.username);
    const counts = normalizedData.map(d => d.count);

    const options = getBaseChartOptions({
      indexAxis: 'y',
      plugins: {
        tooltip: {
          callbacks: {
            title: function (tooltipItems) {
              if (!tooltipItems.length) return '';
              const index = tooltipItems[0].dataIndex;
              const item = normalizedData[index];
              return item ? `Usuario: @${item.username}` : '';
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

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [normalizedData]);

  const periodLabelMap = {
    '24h': 'Últimas 24h',
    '7d': 'Últimos 7 días',
    '30d': 'Últimos 30 días',
    all: 'Historial completo',
  };

  return html`
    <div class="analytics-chart-card">
      <div class="analytics-chart-header">
        <div class="analytics-chart-title-wrap">
          <i class="fas fa-trophy chart-icon icon-gold"></i>
          <div>
            <h4 class="analytics-chart-title">Top 10 Chatters</h4>
            <span class="analytics-chart-subtitle">
              Usuarios más participativos (${periodLabelMap[period] || period})
            </span>
          </div>
        </div>
      </div>
      <div class="analytics-chart-body">
        ${
          normalizedData.length === 0
            ? html`
                <div class="chart-empty-placeholder">
                  <i class="fas fa-user-friends"></i>
                  <p>Sin datos de participación en este período</p>
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
