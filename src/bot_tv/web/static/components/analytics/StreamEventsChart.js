import { html, useEffect, useRef, useMemo } from 'preact-setup';
import { Chart } from '/static/vendor/chart.js-auto.esm.js';
import { getChartTheme, getBaseChartOptions } from './chartTheme.js';

export function StreamEventsChart({ data = null }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  const eventCategories = useMemo(() => {
    const theme = getChartTheme();
    const categories = [
      {
        key: 'subs',
        label: 'Suscripciones',
        color: theme.alertSub,
        aliases: ['subscription', 'sub', 'resub', 'subs'],
        count: 0,
      },
      {
        key: 'gift_subs',
        label: 'Regalos',
        color: theme.alertGiftSub,
        aliases: ['gift_sub', 'sub_gift', 'gifts', 'gift_subs'],
        count: 0,
      },
      {
        key: 'cheers',
        label: 'Bits / Cheers',
        color: theme.alertCheer,
        aliases: ['cheer', 'bits', 'cheers'],
        count: 0,
      },
      {
        key: 'points',
        label: 'Canjes de Puntos',
        color: theme.alertPoints,
        aliases: ['channel_points', 'points', 'redemption', 'canjes'],
        count: 0,
      },
      {
        key: 'raids',
        label: 'Raids',
        color: theme.alertRaid,
        aliases: ['raid', 'raids'],
        count: 0,
      },
      {
        key: 'predictions',
        label: 'Predicciones',
        color: theme.alertPrediction,
        aliases: ['prediction', 'predictions', 'poll'],
        count: 0,
      },
    ];

    if (!data) return [];

    const raw = data.events || data.data || data;

    if (Array.isArray(raw)) {
      raw.forEach(item => {
        const type = (item.type || item.event_type || item.name || '').toLowerCase();
        const cnt = Number(item.count || item.total || 1);
        const match = categories.find(c => c.aliases.includes(type) || type.includes(c.key));
        if (match) {
          match.count += cnt;
        }
      });
    } else if (typeof raw === 'object' && raw !== null) {
      Object.entries(raw).forEach(([typeKey, cntVal]) => {
        const type = typeKey.toLowerCase();
        const cnt = Number(cntVal || 0);
        const match = categories.find(c => c.aliases.includes(type) || type.includes(c.key));
        if (match) {
          match.count += cnt;
        }
      });
    }

    return categories.filter(c => c.count > 0);
  }, [data]);

  const totalEvents = useMemo(() => {
    return eventCategories.reduce((acc, curr) => acc + curr.count, 0);
  }, [eventCategories]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }

    if (eventCategories.length === 0) return;

    const ctx = canvas.getContext('2d');
    const theme = getChartTheme();

    const labels = eventCategories.map(c => c.label);
    const counts = eventCategories.map(c => c.count);
    const bgColors = eventCategories.map(c => c.color);

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
              const val = context.parsed;
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
              return ` ${context.label}: ${val} (${pct}%)`;
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

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [eventCategories]);

  return html`
    <div class="analytics-chart-card">
      <div class="analytics-chart-header">
        <div class="analytics-chart-title-wrap">
          <i class="fas fa-bolt chart-icon icon-events"></i>
          <div>
            <h4 class="analytics-chart-title">Eventos del Directo</h4>
            <span class="analytics-chart-subtitle">
              Desglose de actividad: ${totalEvents} eventos totales
            </span>
          </div>
        </div>
      </div>
      <div class="analytics-chart-body">
        ${
          eventCategories.length === 0
            ? html`
                <div class="chart-empty-placeholder">
                  <i class="fas fa-gift"></i>
                  <p>Sin eventos de directo registrados</p>
                </div>
              `
            : html`
                <div class="analytics-chart-container doughnut-container">
                  <canvas ref=${canvasRef}></canvas>
                </div>
              `
        }
      </div>
    </div>
  `;
}
