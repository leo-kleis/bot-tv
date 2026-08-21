import { html, useState, useEffect, useRef } from 'preact-setup';
import { apiGet, apiPost } from '/static/components/api.js';
import { fmtTime } from 'lib/utils';

export function AgentTab({ conversations = [], dispatch }) {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [rpmInfo, setRpmInfo] = useState(null);
  const feedRef = useRef(null);

  // Cargar estado RPM al montar
  useEffect(() => {
    apiGet('/api/rpm').then(d => {
      if (d.ok && d.data) {
        const statuses = Array.isArray(d.data) ? d.data : d.data.statuses;
        if (statuses?.length) setRpmInfo(statuses[0]);
      }
    });
  }, []);

  async function clearChat() {
    if (loading) return;
    const res = await apiPost('/api/agent/clear', {});
    if (res.ok) {
      dispatch({ type: 'agent_clear_history' });
    }
  }

  // Auto-scroll al final
  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [conversations]);

  async function send() {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput('');
    setLoading(true);

    const ts = new Date().toISOString();

    dispatch({
      type: 'agent_question_pending',
      data: { question: msg, timestamp: ts },
    });

    const data = await apiPost('/api/talk', { message: msg });
    setLoading(false);

    // Recargar RPM después de la consulta
    apiGet('/api/rpm').then(d => {
      if (d.ok && d.data?.length) setRpmInfo(d.data[0]);
    });

    if (!data.ok) {
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
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  const rpm = rpmInfo;
  const rpmDotClass = rpm?.is_blocked ? 'block' : rpm?.rpm_used > 0 ? 'warn' : '';

  return html`
    <div class="agent-tab">
      <!-- Conversación -->
      <div class="agent-convo" ref=${feedRef} id="agent-convo">
        ${
          conversations.length === 0
            ? html`
                <div class="agent-empty">
                  <span class="empty-icon"
                    ><i
                      class="fa-solid fa-robot fa-3x"
                      style="color:var(--text-muted);margin-bottom:12px"
                    ></i
                  ></span>
                  <span style="font-size:13px;color:var(--text-muted)"
                    >Escribe un mensaje para consultar al agente</span
                  >
                </div>
              `
            : conversations.map(
                c => html`
                  <div class="convo-pair" key=${c.id}>
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

      <!-- Info RPM y Limpiar Chat -->
      <div
        class="agent-model-info"
        style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;min-width:0;"
      >
        <div style="display:flex;align-items:center;gap:6px;min-width:0;flex-wrap:wrap;">
          ${
            rpm
              ? html`
                  <span class="rpm-dot ${rpmDotClass}"></span>
                  <span>${rpm.display_name} · ${rpm.rpm_used}/${rpm.rpm_limit} RPM</span>
                  ${
                    rpm.is_blocked
                      ? html`<span style="color:var(--danger)"
                          >Bloqueado
                          ${rpm.next_slot_in ? `(${Math.ceil(rpm.next_slot_in)}s)` : ''}</span
                        >`
                      : null
                  }
                `
              : null
          }
        </div>
        ${
          conversations.length > 0
            ? html`
                <button
                  class="btn btn-secondary"
                  style="padding:4px 10px;font-size:12px;"
                  onClick=${clearChat}
                  title="Borrar conversación y empezar un nuevo chat con el agente"
                >
                  <i class="fa-solid fa-trash" style="margin-right:4px"></i> Limpiar chat
                </button>
              `
            : null
        }
      </div>

      <!-- Input -->
      <div class="agent-input-area">
        <textarea
          id="agent-input"
          placeholder="Pregunta algo al agente..."
          value=${input}
          onInput=${e => setInput(e.target.value)}
          onKeyDown=${onKeyDown}
          rows="2"
          style="flex:1;min-height:42px;max-height:120px;resize:none;min-width:0;"
          disabled=${loading}
        ></textarea>
        <button
          id="btn-agent-send"
          class="btn btn-primary"
          style="align-self:flex-end;min-width:44px;padding:9px 14px"
          onClick=${send}
          disabled=${loading || !input.trim()}
        >
          ${loading ? html`<span class="spinner"></span>` : '↑'}
        </button>
      </div>
    </div>
  `;
}
