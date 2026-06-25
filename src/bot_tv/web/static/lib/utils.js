// Convierte color_rgb [r,g,b] a string CSS rgb(...)
export function toRgb(rgb) {
  if (!rgb || rgb.length < 3) return 'var(--text)';
  return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
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
