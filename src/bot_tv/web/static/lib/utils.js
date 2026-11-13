/** @type {Map<string, string>} */
const RGB_CACHE = new Map();
const MAX_RGB_CACHE = 2000;

/**
 * Convierte `[r, g, b]` a un color legible para tema oscuro (Dark Mode).
 * @param {number[] | null | undefined} rgb
 * @returns {string}
 */
export function toRgb(rgb) {
  if (!rgb || rgb.length < 3) return 'var(--accent-text)';

  const cacheKey = `${rgb[0]},${rgb[1]},${rgb[2]}`;
  const cached = RGB_CACHE.get(cacheKey);
  if (cached !== undefined) return cached;

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

  // Normalización para tema oscuro: limitar saturación y ajustar luminosidad
  s = Math.min(s, 0.72);
  l = Math.max(0.68, Math.min(0.8, l));

  /**
   * @param {number} pVal
   * @param {number} qVal
   * @param {number} t
   * @returns {number}
   */
  const hue2rgb = (pVal, qVal, t) => {
    let tVal = t;
    if (tVal < 0) tVal += 1;
    if (tVal > 1) tVal -= 1;
    if (tVal < 1 / 6) return pVal + (qVal - pVal) * 6 * tVal;
    if (tVal < 1 / 2) return qVal;
    if (tVal < 2 / 3) return pVal + (qVal - pVal) * (2 / 3 - tVal) * 6;
    return pVal;
  };

  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;

  const rOut = Math.round(hue2rgb(p, q, h + 1 / 3) * 255);
  const gOut = Math.round(hue2rgb(p, q, h) * 255);
  const bOut = Math.round(hue2rgb(p, q, h - 1 / 3) * 255);

  const result = `rgb(${rOut}, ${gOut}, ${bOut})`;
  if (RGB_CACHE.size >= MAX_RGB_CACHE) {
    const firstKey = RGB_CACHE.keys().next().value;
    if (firstKey !== undefined) RGB_CACHE.delete(firstKey);
  }
  RGB_CACHE.set(cacheKey, result);
  return result;
}

/**
 * Formatea HH:MM desde un timestamp ISO.
 * @param {string | number | Date | null | undefined} iso
 * @returns {string}
 */
export function fmtTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  } catch {
    return '';
  }
}

/**
 * Valida que una URL utilice protocolo http: o https:.
 * @param {string | null | undefined} url
 * @returns {string}
 */
export function sanitizeHttpUrl(url) {
  if (!url || typeof url !== 'string') return '';
  try {
    const baseOrigin = typeof window !== 'undefined' ? window.location.origin : undefined;
    const parsed = new URL(url, baseOrigin);
    if (parsed.protocol === 'https:' || parsed.protocol === 'http:') {
      return parsed.href;
    }
    return '';
  } catch {
    return '';
  }
}
