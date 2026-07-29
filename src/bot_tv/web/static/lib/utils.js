// Convierte color_rgb [r,g,b] a un color suave y altamente legible para tema oscuro (Dark Mode)
export function toRgb(rgb) {
  if (!rgb || rgb.length < 3) return 'var(--accent-text)';

  let [r, g, b] = rgb;
  r /= 255;
  g /= 255;
  b /= 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  let l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0);
        break;
      case g:
        h = (b - r) / d + 2;
        break;
      case b:
        h = (r - g) / d + 4;
        break;
    }
    h /= 6;
  }

  // Normalización para tema oscuro:
  // 1. Limitar saturación máxima para evitar colores de neón estridentes (máx 72%)
  s = Math.min(s, 0.72);
  // 2. Ajustar luminosidad para visibilidad óptima (entre 68% y 80%)
  l = Math.max(0.68, Math.min(0.8, l));

  const hue2rgb = (p, q, t) => {
    let tVal = t;
    if (tVal < 0) tVal += 1;
    if (tVal > 1) tVal -= 1;
    if (tVal < 1 / 6) return p + (q - p) * 6 * tVal;
    if (tVal < 1 / 2) return q;
    if (tVal < 2 / 3) return p + (q - p) * (2 / 3 - tVal) * 6;
    return p;
  };

  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;

  const rOut = Math.round(hue2rgb(p, q, h + 1 / 3) * 255);
  const gOut = Math.round(hue2rgb(p, q, h) * 255);
  const bOut = Math.round(hue2rgb(p, q, h - 1 / 3) * 255);

  return `rgb(${rOut}, ${gOut}, ${bOut})`;
}

// Formatea HH:MM desde ISO timestamp
export function fmtTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  } catch {
    return '';
  }
}
