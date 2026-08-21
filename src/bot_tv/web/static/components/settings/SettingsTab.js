import { html, useState, useEffect } from 'preact-setup';
import { apiGet, apiPost } from '/static/components/api.js';
import { ModelSection } from '/static/components/actions/ModelSection.js';
import { DangerSection } from '/static/components/actions/DangerSection.js';

const MIN_FONT = 12;
const MAX_FONT = 22;
const STEP = 0.5;

export function SettingsTab({ dispatch }) {
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

  const [contextLimit, setContextLimit] = useState(0);
  const [savingLimit, setSavingLimit] = useState(false);
  const [limitSavedMsg, setLimitSavedMsg] = useState('');

  const [hideBots, setHideBots] = useState(
    () => localStorage.getItem('hide-bot-messages') === 'true'
  );

  const handleHideBotsChange = e => {
    const val = e.target.checked;
    setHideBots(val);
    localStorage.setItem('hide-bot-messages', String(val));
    window.dispatchEvent(new Event('storage-settings-changed'));
  };

  useEffect(() => {
    apiGet('/api/rpm').then(d => {
      if (d.ok && d.data) {
        if (typeof d.data.context_limit === 'number') {
          setContextLimit(d.data.context_limit);
        }
      }
    });
  }, []);

  async function handleContextLimitChange(newVal) {
    const val = Math.max(0, parseInt(newVal, 10) || 0);
    setContextLimit(val);
    setSavingLimit(true);
    setLimitSavedMsg('');

    const res = await apiPost('/api/agent/context_limit', { limit: val });
    setSavingLimit(false);
    if (res.ok) {
      setLimitSavedMsg('Guardado');
      setTimeout(() => setLimitSavedMsg(''), 2000);
    }
  }

  const updateFontSize = newSize => {
    const size = Math.max(MIN_FONT, Math.min(MAX_FONT, newSize));
    setFontSize(size);
    const sizeStr = `${size}px`;
    localStorage.setItem('font-size', sizeStr);
    document.documentElement.style.setProperty('--font-size', sizeStr);
  };

  const handleDecrease = () => updateFontSize(fontSize - STEP);
  const handleIncrease = () => updateFontSize(fontSize + STEP);
  const handleSliderChange = e => updateFontSize(parseFloat(e.target.value));

  const getLabel = size => {
    if (size <= 13) return 'Pequeño';
    if (size <= 15) return 'Normal';
    if (size <= 17) return 'Mediano';
    if (size <= 19) return 'Grande';
    return 'Muy Grande';
  };

  return html`
    <div class="settings-tab">
      <!-- Sección Agente -->
      <div class="settings-section">
        <h3 class="settings-section-title">
          <i class="fa-solid fa-robot"></i> Configuración del Agente de IA
        </h3>

        <!-- Selección de Modelo -->
        <div style="margin-bottom: 20px;">
          <${ModelSection} />
        </div>

        <!-- Límite de Contexto -->
        <div class="settings-control-group">
          <label class="settings-label" for="context-limit-input">
            Límite de Contexto de Conversación (Turnos)
          </label>
          <div
            style="display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin-top:6px;min-width:0;"
          >
            <input
              id="context-limit-input"
              type="number"
              min="0"
              max="100"
              value=${contextLimit}
              onInput=${e => handleContextLimitChange(e.target.value)}
              style="width:100px;padding:6px 10px;border-radius:4px;border:1px solid var(--border);background:var(--surface);color:var(--text);font-size:14px;"
            />
            <span style="font-size:12px;color:var(--text-muted);">
              ${
                contextLimit === 0
                  ? '0 = Sin Límite (Ilimitado)'
                  : `Conserva los últimos ${contextLimit} turnos`
              }
            </span>
            ${
              savingLimit
                ? html`<span class="spinner" style="border-top-color:var(--accent)"></span>`
                : null
            }
            ${
              limitSavedMsg
                ? html`<span style="color:var(--success);font-size:12px;font-weight:600;"
                    >${limitSavedMsg}</span
                  >`
                : null
            }
          </div>
        </div>
      </div>

      <!-- Sección Chat -->
      <div class="settings-section">
        <h3 class="settings-section-title">
          <i class="fa-solid fa-comments"></i> Personalización de Chat
        </h3>

        <div class="settings-control-group">
          <span class="settings-label">Tamaño de la Fuente del Chat</span>

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

          <div
            style="margin-top: 12px; display: flex; align-items: center; gap: 12px; width: 100%; min-width: 0;"
          >
            <input
              type="range"
              min=${MIN_FONT}
              max=${MAX_FONT}
              step=${STEP}
              value=${fontSize}
              onInput=${handleSliderChange}
              style="flex: 1; min-width: 0; accent-color: var(--accent); cursor: pointer;"
              aria-label="Selector deslizante de tamaño de letra"
            />
            <span
              style="font-size: 12px; color: var(--text-muted); font-weight: 600; min-width: 65px; text-align: right;"
            >
              ${getLabel(fontSize)}
            </span>
          </div>

          <div class="font-preview-box">
            <span class="font-preview-label">Previsualización del Chat</span>

            <div
              class="chat-feed"
              style="background: transparent; padding: 0; pointer-events: none;"
            >
              <div class="chat-msg-group">
                <div
                  class="user-avatar user-avatar--md"
                  style="background: rgba(130, 87, 229, 0.2); color: var(--accent-text);"
                >
                  S
                </div>
                <div class="chat-msg-content">
                  <div class="chat-msg-header">
                    <span class="chat-author" style="color: var(--accent-text)">
                      <span class="chat-nickname">Streamer</span>
                    </span>
                    <span class="chat-role">(Broadcaster)</span>
                    <span class="chat-time">18:48</span>
                  </div>
                  <div class="chat-msg-body">
                    Este es un mensaje de prueba para ver el tamaño de la fuente. ¿Qué tal se ve?
                  </div>
                </div>
              </div>

              <div class="chat-msg-group is-bot">
                <div
                  class="user-avatar user-avatar--md"
                  style="background: rgba(245, 158, 11, 0.2); color: var(--warning);"
                >
                  A
                </div>
                <div class="chat-msg-content">
                  <div class="chat-msg-header">
                    <span class="chat-author" style="color: var(--warning)">
                      <span class="chat-nickname">Agente</span>
                    </span>
                    <span class="chat-role">(Bot)</span>
                    <span class="chat-time">18:48</span>
                  </div>
                  <div class="chat-msg-body">
                    Respondiendo a tu consulta con el tamaño de letra dinámico configurado.
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="settings-toggle-row">
            <input
              type="checkbox"
              class="role-toggle-checkbox"
              checked=${hideBots}
              onChange=${handleHideBotsChange}
              aria-label="Ocultar mensajes de usuarios BOT en el chat"
            />
            <div class="settings-toggle-info">
              <span class="settings-label">Ocultar mensajes de usuarios BOT</span>
              <span class="settings-subtext"
                >No muestra los mensajes de usuarios etiquetados como Bot en el chat</span
              >
            </div>
          </div>
        </div>
      </div>

      <!-- Sección Apagar Bot -->
      <${DangerSection} dispatch=${dispatch} />
    </div>
  `;
}
