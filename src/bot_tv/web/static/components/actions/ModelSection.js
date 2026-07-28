import { html, useState, useEffect } from 'preact-setup';
import { apiGet, apiPost } from '/static/components/api.js';
import { CustomSelect } from '/static/components/CustomSelect.js';

export function ModelSection() {
  const [models, setModels] = useState([]);
  const [selected, setSelected] = useState('');
  const [rpm, setRpm] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiGet('/api/models').then(d => {
      if (d.ok && d.data) {
        setModels(d.data.filter(m => m.enabled));
      }
    });
    apiGet('/api/rpm').then(d => {
      if (d.ok && d.data) {
        const statuses = Array.isArray(d.data) ? d.data : d.data.statuses;
        if (statuses?.length) {
          setRpm(statuses[0]);
          setSelected(statuses[0].model);
        }
      }
    });
  }, []);

  async function switchModel() {
    if (!selected || loading) return;
    setLoading(true);
    setResult(null);
    const data = await apiPost('/api/switch_model', { model: selected });
    setLoading(false);
    if (data.ok) {
      setResult({ ok: true, msg: data.data.message });
      if (data.data.current_model) {
        setSelected(data.data.current_model);
      }
      apiGet('/api/rpm').then(d => {
        if (d.ok && d.data) {
          const statuses = Array.isArray(d.data) ? d.data : d.data.statuses;
          if (statuses?.length) setRpm(statuses[0]);
        }
      });
    } else {
      setResult({ ok: false, msg: data.error || 'Error.' });
    }
  }

  return html`
    <div class="section">
      <div class="section-header">
        <span class="section-icon"><i class="fa-solid fa-brain"></i></span> Modelo IA
      </div>
      <div class="section-body">
        ${
          rpm
            ? html`
                <div
                  style="font-size:12px;color:var(--text-muted);display:flex;gap:8px;align-items:center"
                >
                  <span style="color:var(--text)"
                    >Activo:
                    <strong style="color:var(--accent-text)">${rpm.display_name}</strong></span
                  >
                  <span>·</span>
                  <span>${rpm.rpm_used}/${rpm.rpm_limit} RPM</span>
                  ${rpm.is_blocked ? html`<span style="color:var(--danger)">BLOQUEADO</span>` : null}
                </div>
              `
            : null
        }

        <div class="action-row">
          <div class="model-select-wrap">
            <${CustomSelect}
              id="select-model"
              value=${selected}
              onChange=${setSelected}
              options=${models.map(m => ({
                value: m.name,
                label: `${m.display_name} (${m.rpm_limit} RPM)`,
              }))}
              disabled=${loading}
            />
          </div>
          <button
            id="btn-switch-model"
            class="btn btn-primary"
            onClick=${switchModel}
            disabled=${!selected || loading || selected === rpm?.model}
          >
            ${loading ? html`<span class="spinner"></span>` : 'Cambiar'}
          </button>
        </div>

        ${
          result
            ? html`<div class="result-msg ${result.ok ? 'ok' : 'err'}">${result.msg}</div>`
            : null
        }
      </div>
    </div>
  `;
}
