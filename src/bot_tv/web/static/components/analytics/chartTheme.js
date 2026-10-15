/**
 * chartTheme.js — Paleta y configuración base para gráficos con Chart.js
 * Basado en las variables CSS del proyecto (variables.css).
 */

export function getChartTheme() {
  const root = typeof window !== 'undefined' ? getComputedStyle(document.documentElement) : null;
  const getVar = (name, fallback) => {
    if (!root) return fallback;
    const val = root.getPropertyValue(name).trim();
    return val || fallback;
  };

  return {
    primary: getVar('--color-primary', getVar('--accent', '#a970ff')),
    accent: getVar('--color-accent', getVar('--accent-dim', '#8c4eeb')),
    accentGlow: getVar('--accent-glow', 'rgba(169, 112, 255, 0.15)'),
    accentText: getVar('--accent-text', '#d8c4ff'),
    bgCard: getVar('--bg-card', getVar('--surface2-solid', '#1a1624')),
    surface: getVar('--surface', 'rgba(18, 16, 23, 0.75)'),
    surface2: getVar('--surface2', 'rgba(26, 22, 36, 0.8)'),
    surface3: getVar('--surface3', '#251d33'),
    borderColor: getVar('--border-color', getVar('--border', 'rgba(169, 112, 255, 0.18)')),
    borderLight: getVar('--border-light', 'rgba(255, 255, 255, 0.08)'),
    textMain: getVar('--text-main', getVar('--text', '#f5f4f8')),
    textMuted: getVar('--text-muted', '#938ea5'),
    online: getVar('--online', '#34d399'),
    warning: getVar('--warning', '#fbbf24'),
    danger: getVar('--danger', '#f87171'),
    success: getVar('--success', '#34d399'),
    fontFamily: getVar('--font', "'Outfit', -apple-system, BlinkMacSystemFont, sans-serif"),
    // Paleta de eventos del directo
    alertSub: getVar('--alert-sub', '#4ade80'),
    alertCheer: getVar('--alert-cheer', '#facc15'),
    alertPoints: getVar('--alert-points', '#38bdf8'),
    alertRaid: getVar('--alert-raid', '#e879f9'),
    alertPrediction: getVar('--alert-prediction', '#c084fc'),
    alertGiftSub: '#22c55e',
  };
}

export function createAreaGradient(ctx, colorStart, colorEnd, height = 260) {
  if (!ctx || typeof ctx.createLinearGradient !== 'function') {
    return colorStart;
  }
  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, colorStart);
  gradient.addColorStop(1, colorEnd);
  return gradient;
}

export function getBaseChartOptions(overrides = {}) {
  const theme = getChartTheme();

  const base = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 400,
      easing: 'easeOutQuart',
    },
    layout: {
      padding: {
        top: 8,
        bottom: 4,
        left: 4,
        right: 8,
      },
    },
    plugins: {
      legend: {
        display: false,
        labels: {
          color: theme.textMuted,
          font: {
            family: theme.fontFamily,
            size: 11,
          },
        },
      },
      tooltip: {
        enabled: true,
        backgroundColor: 'rgba(18, 16, 23, 0.95)',
        titleColor: theme.textMain,
        bodyColor: '#cfcbd8',
        borderColor: theme.borderColor,
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
        displayColors: true,
        boxPadding: 4,
        titleFont: {
          family: theme.fontFamily,
          weight: '600',
          size: 12,
        },
        bodyFont: {
          family: theme.fontFamily,
          size: 12,
        },
      },
    },
    scales: {
      x: {
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
          maxRotation: 0,
          autoSkip: true,
          autoSkipPadding: 12,
        },
        border: {
          display: false,
        },
      },
      y: {
        beginAtZero: true,
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
    },
  };

  // Fusión superficial y de plugins/scales si se especifican
  const merged = { ...base, ...overrides };
  if (overrides.plugins) {
    merged.plugins = {
      ...base.plugins,
      ...overrides.plugins,
      tooltip: { ...base.plugins.tooltip, ...overrides.plugins.tooltip },
      legend: { ...base.plugins.legend, ...overrides.plugins.legend },
    };
  }
  if (overrides.scales) {
    merged.scales = {
      ...base.scales,
      ...overrides.scales,
    };
  }
  return merged;
}
