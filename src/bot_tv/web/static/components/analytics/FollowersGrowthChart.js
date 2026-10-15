import { html, useEffect, useRef, useMemo } from 'preact-setup';
import { Chart } from '/static/vendor/chart.js-auto.esm.js';
import { getChartTheme, createAreaGradient, getBaseChartOptions } from './chartTheme.js';

function formatDisplayDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    return `${day}/${month}`;
  } catch {
    return dateStr;
  }
}

export function FollowersGrowthChart({ data = [], period = 'day' }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  const normalizedData = useMemo(() => {
    const rawList = Array.isArray(data)
      ? data
      : (data && (data.growth || data.data || data.points)) || [];

    if (!rawList || rawList.length === 0) return [];

    return rawList.map(item => {
      const rawDate = item.date || item.day || item.timestamp || '';
      const net =
        item.net != null
          ? Number(item.net)
          : Number(item.count != null ? item.count : item.total || 0);
      const gained = item.gained != null ? Number(item.gained) : null;
      const lost = item.lost != null ? Number(item.lost) : null;

      return {
        rawDate,
        label: formatDisplayDate(rawDate),
        net,
        gained,
        lost,
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

    const areaGradient = createAreaGradient(
      ctx,
      'rgba(52, 211, 153, 0.35)',
      'rgba(52, 211, 153, 0.01)',
      240
    );

    const labels = normalizedData.map(d => d.label);
    const values = normalizedData.map(d => d.net);

    const options = getBaseChartOptions({
      plugins: {
        tooltip: {
          callbacks: {
            title: function (tooltipItems) {
              if (!tooltipItems.length) return '';
              const index = tooltipItems[0].dataIndex;
              const item = normalizedData[index];
              return item ? `Fecha: ${item.rawDate || item.label}` : '';
            },
            label: function (context) {
              const item = normalizedData[context.dataIndex];
              const netVal = context.parsed.y;
              const sign = netVal > 0 ? '+' : '';
              let txt = ` Balance neto: ${sign}${netVal} seguidores`;
              if (item && (item.gained != null || item.lost != null)) {
                txt += ` (+${item.gained || 0} / -${item.lost || 0})`;
              }
              return txt;
            },
          },
        },
      },
      scales: {
        x: {
          title: {
            display: true,
            text: 'Días registrados',
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
            text: 'Crecimiento neto',
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
            label: 'Seguidores netos',
            data: values,
            borderColor: theme.online,
            borderWidth: 2,
            backgroundColor: areaGradient,
            fill: true,
            tension: 0.25,
            pointRadius: 3,
            pointHoverRadius: 6,
            pointBackgroundColor: theme.online,
            pointBorderColor: '#ffffff',
            pointBorderWidth: 1.5,
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

  return html`
    <div class="analytics-chart-card">
      <div class="analytics-chart-header">
        <div class="analytics-chart-title-wrap">
          <i class="fas fa-chart-line chart-icon icon-growth"></i>
          <div>
            <h4 class="analytics-chart-title">Evolución de Seguidores</h4>
            <span class="analytics-chart-subtitle">
              Variación neta registrada por ${period === 'day' ? 'día' : period}
            </span>
          </div>
        </div>
      </div>
      <div class="analytics-chart-body">
        ${
          normalizedData.length === 0
            ? html`
                <div class="chart-empty-placeholder">
                  <i class="fas fa-user-plus"></i>
                  <p>Sin fluctuaciones de seguidores registradas</p>
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
