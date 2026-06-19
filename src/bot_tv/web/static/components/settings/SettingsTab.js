import { h, useState, useEffect } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';

const html = htm.bind(h);

const MIN_FONT = 12;
const MAX_FONT = 22;
const STEP = 0.5;

export function SettingsTab() {
  const [fontSize, setFontSize] = useState(() => {
    const saved = localStorage.getItem('font-size');
    if (saved) {
      const parsed = parseFloat(saved);
      if (!isNaN(parsed) && parsed >= MIN_FONT && parsed <= MAX_FONT) {
        return parsed;
      }
    }
    return 14.5; // Valor por defecto
  });

  const updateFontSize = (newSize) => {
    const size = Math.max(MIN_FONT, Math.min(MAX_FONT, newSize));
    setFontSize(size);
    const sizeStr = `${size}px`;
    localStorage.setItem('font-size', sizeStr);
    document.documentElement.style.setProperty('--font-size', sizeStr);
  };

  const handleDecrease = () => updateFontSize(fontSize - STEP);
  const handleIncrease = () => updateFontSize(fontSize + STEP);
  const handleSliderChange = (e) => updateFontSize(parseFloat(e.target.value));

  const getLabel = (size) => {
    if (size <= 13) return 'Pequeño';
    if (size <= 15) return 'Normal';
    if (size <= 17) return 'Mediano';
    if (size <= 19) return 'Grande';
    return 'Muy Grande';
  };

  return html`
    <div class="settings-tab">
      <div class="settings-section">
        <h3 class="settings-section-title">
          <i class="fa-solid fa-sliders"></i> Personalización de Estilo
        </h3>

        <div class="settings-control-group">
          <span class="settings-label">Tamaño de la Fuente</span>
          
          <div class="font-size-controls">
            <button 
              class="font-btn" 
              onClick=${handleDecrease} 
              disabled=${fontSize <= MIN_FONT}
              title="Disminuir tamaño"
              aria-label="Disminuir tamaño de letra"
            >
              <i class="fa-solid fa-minus"></i>
            </button>
            
            <span class="font-current-val">${fontSize.toFixed(1)} px</span>
            
            <button 
              class="font-btn" 
              onClick=${handleIncrease} 
              disabled=${fontSize >= MAX_FONT}
              title="Aumentar tamaño"
              aria-label="Aumentar tamaño de letra"
            >
              <i class="fa-solid fa-plus"></i>
            </button>
          </div>

          <div style="margin-top: 12px; display: flex; align-items: center; gap: 12px; width: 100%;">
            <input 
              type="range" 
              min=${MIN_FONT} 
              max=${MAX_FONT} 
              step=${STEP} 
              value=${fontSize} 
              onInput=${handleSliderChange}
              style="flex: 1; accent-color: var(--accent); cursor: pointer;"
              aria-label="Selector deslizante de tamaño de letra"
            />
            <span style="font-size: 12px; color: var(--text-muted); font-weight: 600; min-width: 65px; text-align: right;">
              ${getLabel(fontSize)}
            </span>
          </div>
        </div>

        <div class="font-preview-box">
          <span class="font-preview-label">Previsualización</span>
          
          <div class="font-preview-chat">
            <span class="user">Streamer:</span>
            <span class="font-preview-text">Este es un mensaje de prueba para ver el tamaño de la fuente. ¿Qué tal se ve?</span>
          </div>

          <div class="font-preview-chat" style="background: var(--surface2)">
            <span class="user" style="color: var(--warning)">Agente:</span>
            <span class="font-preview-text">Respondiendo a tu consulta con tamaño de letra dinámico.</span>
          </div>
        </div>
      </div>
    </div>
  `;
}
