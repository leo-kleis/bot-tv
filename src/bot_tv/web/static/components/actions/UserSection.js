import { html, useState } from 'preact-setup';
import { apiPost } from '/static/components/api.js';
import { UserAutocomplete } from '/static/components/actions/UserAutocomplete.js';

export function UserSection() {
  const [username, setUsername] = useState('');
  const [nickname, setNickname] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState('');

  async function toggleBot() {
    if (!username.trim()) return;
    setLoading('bot');
    setResult(null);
    const data = await apiPost('/api/toggle_bot', { username: username.trim() });
    setLoading('');
    if (data.ok) {
      const state = data.data.is_bot ? 'marcado como bot ✓' : 'desmarcado de bot ✓';
      setResult({ ok: true, msg: `${data.data.username} ${state}` });
    } else {
      setResult({ ok: false, msg: data.error || 'Error.' });
    }
  }

  async function setNick() {
    if (!username.trim()) return;
    setLoading('nick');
    setResult(null);
    const data = await apiPost('/api/set_nickname', {
      username: username.trim(),
      nickname: nickname.trim() || null,
    });
    setLoading('');
    if (data.ok) {
      const msg = data.data.nickname
        ? `Apodo de ${data.data.username} → "${data.data.nickname}"`
        : `Apodo de ${data.data.username} eliminado`;
      setResult({ ok: true, msg });
      setNickname('');
    } else {
      setResult({ ok: false, msg: data.error || 'Error.' });
    }
  }

  return html`
    <div class="section">
      <div class="section-header">
        <span class="section-icon"><i class="fa-solid fa-user-gear"></i></span> Gestión de Usuario
      </div>
      <div class="section-body">
        <div>
          <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:5px"
            >Usuario</label
          >
          <${UserAutocomplete}
            id="input-username"
            value=${username}
            onChange=${setUsername}
            placeholder="Buscar usuario..."
          />
        </div>

        <div class="action-row">
          <button
            id="btn-toggle-bot"
            class="btn"
            style="flex:1"
            onClick=${toggleBot}
            disabled=${!username.trim() || loading === 'bot'}
          >
            ${loading === 'bot'
              ? html`<span class="spinner"></span>`
              : html`<i class="fa-solid fa-robot"></i> Toggle Bot`}
          </button>
        </div>

        <div>
          <label style="font-size:11px;color:var(--text-muted);display:block;margin-bottom:5px"
            >Apodo (vacío = eliminar)</label
          >
          <div class="action-row">
            <input
              id="input-nickname"
              type="text"
              placeholder="Nuevo apodo..."
              value=${nickname}
              onInput=${e => setNickname(e.target.value)}
              style="flex:1"
            />
            <button
              id="btn-set-nickname"
              class="btn btn-primary"
              onClick=${setNick}
              disabled=${!username.trim() || loading === 'nick'}
            >
              ${loading === 'nick' ? html`<span class="spinner"></span>` : 'Guardar'}
            </button>
          </div>
        </div>

        ${result
          ? html`<div class="result-msg ${result.ok ? 'ok' : 'err'}">${result.msg}</div>`
          : null}
      </div>
    </div>
  `;
}
