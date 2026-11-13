import { html, useState, useEffect, useRef, useMemo } from 'preact-setup';
import { apiGet, apiPost } from '/static/components/api.js';
import { fmtTime } from 'lib/utils';
import { ComposerBar } from '../ComposerBar.js';
import { DisplaySettingsMenu } from '../DisplaySettingsMenu.js';

/**
 * @typedef {{
 *   timestamp: string,
 *   question: string,
 *   response?: string | null,
 *   model?: string,
 * }} AgentConversation
 */

/**
 * @typedef {{
 *   name: string,
 *   display_name: string,
 *   rpm_limit: number,
 *   enabled?: boolean,
 * }} ModelInfo
 */

/**
 * @typedef {{
 *   model: string,
 *   display_name: string,
 *   rpm_used: number,
 *   rpm_limit: number,
 *   is_blocked?: boolean,
 *   next_slot_in?: number,
 * }} RpmStatus
 */

/**
 * @param {{
 *   conversations?: AgentConversation[],
 *   dispatch?: (action: Record<string, unknown>) => void,
 * }} props
 */
export function AgentTab({ conversations = [], dispatch }) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [switchingModel, setSwitchingModel] = useState(false);
  const [rpmInfo, setRpmInfo] = useState(/** @type {RpmStatus | null} */ (null));
  const [models, setModels] = useState(/** @type {ModelInfo[]} */ ([]));
  const feedRef = useRef(/** @type {HTMLDivElement | null} */ (null));
  const inputRef = useRef(/** @type {HTMLTextAreaElement | null} */ (null));
  const isMountedRef = useRef(true);
  const rpmControllerRef = useRef(/** @type {AbortController | null} */ (null));

  // Cargar estado RPM y lista de modelos al montar
  useEffect(() => {
    isMountedRef.current = true;
    const controller = new AbortController();

    apiGet('/api/rpm', { signal: controller.signal })
      .then(d => {
        if (controller.signal.aborted || !isMountedRef.current) return;
        if (d.ok && d.data) {
          const statuses = Array.isArray(d.data) ? d.data : d.data.statuses;
          if (statuses?.length) setRpmInfo(statuses[0]);
        }
      })
      .catch(() => {});

    apiGet('/api/models', { signal: controller.signal })
      .then(d => {
        if (controller.signal.aborted || !isMountedRef.current) return;
        if (d.ok && Array.isArray(d.data)) {
          setModels(d.data.filter(m => m.enabled !== false));
        }
      })
      .catch(() => {});

    return () => {
      isMountedRef.current = false;
      controller.abort();
      if (rpmControllerRef.current) {
        rpmControllerRef.current.abort();
      }
    };
  }, []);

  async function clearChat() {
    if (loading) return;
    const res = await apiPost('/api/agent/clear', {});
    if (res.ok && dispatch) {
      dispatch({ type: 'agent_clear_history' });
    }
  }

  // Auto-scroll al final cuando llegan nuevas respuestas
  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [conversations]);

  async function refreshRpm() {
    if (rpmControllerRef.current) {
      rpmControllerRef.current.abort();
    }
    const rpmController = new AbortController();
    rpmControllerRef.current = rpmController;
    try {
      const d = await apiGet('/api/rpm', { signal: rpmController.signal });
      if (rpmController.signal.aborted || !isMountedRef.current) return;
      if (d.ok && d.data) {
        const statuses = Array.isArray(d.data) ? d.data : d.data?.statuses;
        if (statuses?.length) setRpmInfo(statuses[0]);
      }
    } catch {
      // Ignorar abortos
    }
  }

  /**
   * @param {string} newModel
   */
  async function handleModelChange(newModel) {
    if (!newModel || switchingModel || newModel === rpmInfo?.model) return;
    setSwitchingModel(true);
    const data = await apiPost('/api/switch_model', { model: newModel });
    if (!isMountedRef.current) return;
    setSwitchingModel(false);

    if (data.ok) {
      await refreshRpm();
      if (dispatch) {
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: Date.now().toString(),
            type: 'success',
            data: { message: data.data?.message || 'Modelo actualizado.' },
          },
        });
      }
    } else if (dispatch) {
      dispatch({
        type: 'ADD_TOAST',
        toast: {
          id: Date.now().toString(),
          type: 'api_error',
          data: { message: data.error || 'No se pudo cambiar el modelo.' },
        },
      });
    }
  }

  async function send() {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput('');
    setLoading(true);

    const ts = new Date().toISOString();

    if (dispatch) {
      dispatch({
        type: 'agent_question_pending',
        data: { question: msg, timestamp: ts },
      });
    }

    const data = await apiPost('/api/talk', { message: msg });
    if (!isMountedRef.current) return;
    setLoading(false);

    refreshRpm();

    if (!data.ok && dispatch) {
      dispatch({
        type: 'agent_response',
        data: {
          timestamp: ts,
          question: msg,
          response: `Error: ${data.error}`,
          model: 'error',
        },
      });
    }

    requestAnimationFrame(() => {
      if (inputRef.current && isMountedRef.current) {
        inputRef.current.focus();
      }
    });
  }

  const modelOptions = useMemo(
    () =>
      models.map(m => ({
        value: m.name,
        label: m.display_name || m.name,
      })),
    [models]
  );

  const rpm = rpmInfo;
  const rpmDotClass = rpm?.is_blocked ? 'block' : rpm && rpm.rpm_used > 0 ? 'warn' : '';

  const rpmMetaContent = rpm
    ? html`
        <span class="composer-rpm-badge ${rpm.is_blocked ? 'is-blocked' : ''}">
          ${rpm.rpm_used}/${rpm.rpm_limit}
          RPM${rpm.is_blocked && rpm.next_slot_in ? ` · ${Math.ceil(rpm.next_slot_in)}s` : ''}
        </span>
      `
    : null;

  return html`
    <div class="agent-tab">
      <div class="agent-header">
        <div class="agent-header-title">
          <i class="fa-solid fa-robot" aria-hidden="true"></i>
          <span>Agente IA</span>
        </div>
        <div class="agent-header-actions">
          <${DisplaySettingsMenu} showHideBots=${false} buttonId="agent-display-btn" />
          ${
            conversations.length > 0
              ? html`
                  <button
                    type="button"
                    class="btn btn-secondary btn-sm"
                    onClick=${clearChat}
                    disabled=${loading}
                    title="Borrar conversación y empezar un nuevo chat con el agente"
                  >
                    <i class="fa-solid fa-trash" aria-hidden="true"></i> Limpiar chat
                  </button>
                `
              : null
          }
        </div>
      </div>

      <div
        class="agent-convo agent-feed"
        ref=${feedRef}
        id="agent-convo"
        style="font-size: var(--font-size, 14px);"
      >
        ${
          conversations.length === 0
            ? html`
                <div class="agent-empty">
                  <span class="empty-icon">
                    <i
                      class="fa-solid fa-robot fa-3x"
                      style="color:var(--text-muted);margin-bottom:12px"
                      aria-hidden="true"
                    ></i>
                  </span>
                  <span style="font-size:13px;color:var(--text-muted)">
                    Escribe un mensaje para consultar al agente
                  </span>
                </div>
              `
            : conversations.map(
                c => html`
                  <div class="convo-pair" key=${c.timestamp}>
                    <div class="convo-q">${c.question}</div>
                    ${
                      c.response == null
                        ? html`<div class="convo-a loading">
                            <span class="spinner" style="border-top-color:var(--accent)"></span>
                            Pensando...
                          </div>`
                        : html`
                            <div class="convo-a">${c.response}</div>
                            <div class="convo-meta">
                              ${fmtTime(c.timestamp)}${c.model ? ` · ${c.model}` : ''}
                            </div>
                          `
                    }
                  </div>
                `
              )
        }
      </div>

      <div class="mi-tab-fixed-bottom">
        <${ComposerBar}
          value=${input}
          onChange=${setInput}
          onSubmit=${send}
          placeholder="Pregunta algo al agente..."
          ariaLabel="Pregunta algo al agente"
          submitAriaLabel="Enviar mensaje al agente"
          disabled=${loading}
          sending=${loading}
          sendDisabled=${loading || !input.trim()}
          multiline=${true}
          inputRef=${inputRef}
          inputId="agent-input"
          submitId="btn-agent-send"
          selectId="agent-model-select"
          selectOptions=${modelOptions}
          selectValue=${rpm?.model || ''}
          onSelectChange=${handleModelChange}
          selectAriaLabel="Seleccionar modelo de IA"
          selectDisabled=${loading || switchingModel || modelOptions.length === 0}
          selectPlaceholder="Modelo IA"
          selectTriggerPrefix=${html`<span
            class="rpm-dot ${rpmDotClass}"
            aria-hidden="true"
          ></span>`}
          metaContent=${rpmMetaContent}
        />
      </div>
    </div>
  `;
}
