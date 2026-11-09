import { html, useEffect, useRef, useMemo } from 'preact-setup';
import { Chart } from 'chart.js';
import { getChartTheme, createAreaGradient, getBaseChartOptions } from './chartTheme.js';

function formatTimestampTime(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    const h = String(d.getHours()).padStart(2, '0');
    const m = String(d.getMinutes()).padStart(2, '0');
    const s = String(d.getSeconds()).padStart(2, '0');
    return `${h}:${m}:${s}`;
  } catch {
    return String(isoStr);
  }
}

export function ViewersTimelineChart({ data = [], session = null }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);
  const dataRef = useRef([]);

  // Normalizar puntos de datos
  const normalizedData = useMemo(() => {
    const rawList = Array.isArray(data)
      ? data
      : (data && (data.data || data.timeline || data.points)) || [];

    if (!rawList || rawList.length === 0) return [];

    let startTime = null;
    if (session && session.started_at) {
      startTime = new Date(session.started_at).getTime();
    } else if (rawList[0] && rawList[0].timestamp) {
      startTime = new Date(rawList[0].timestamp).getTime();
    }

    return rawList.map((pt, idx) => {
      const timestamp = pt.timestamp || pt.time || pt.created_at;
      let minute = pt.minute;
      if (minute == null) {
        if (startTime && timestamp) {
          const ptTime = new Date(timestamp).getTime();
          minute = Math.max(0, Math.round((ptTime - startTime) / 60000));
        } else {
          minute = idx * 5;
        }
      }

      const viewers = pt.viewers != null ? Number(pt.viewers) : Number(pt.count || 0);
      const timeStr = timestamp ? formatTimestampTime(timestamp) : '';

      return {
        minute,
        viewers,
        timeStr,
        label: `Min ${minute}`,
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
    const theme = getChartTheme();
    const areaGradient = createAreaGradient(
      ctx,
      'rgba(169, 112, 255, 0.35)',
      'rgba(169, 112, 255, 0.01)',
      240
    );

    const options = getBaseChartOptions({
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
            text: 'Tiempo transcurrido en el directo',
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
            pointHoverRadius: 6,
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
          <i class="fas fa-chart-area chart-icon icon-primary"></i>
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
                  <i class="fas fa-chart-line"></i>
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
