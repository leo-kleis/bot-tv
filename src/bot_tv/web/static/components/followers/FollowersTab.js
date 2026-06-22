import { html, useState } from '/static/lib/preact-setup.js';
import { apiPost } from '/static/components/api.js';

export function FollowersTab({ followers }) {
  const [syncing, setSyncing] = useState(false);
  const [result, setResult]   = useState(null);

  const sync = followers.lastSync;
  const prog = followers.progress;

  async function handleSync() {
    setSyncing(true);
    setResult(null);
    const data = await apiPost('/api/sync_followers', {});
    setSyncing(false);
    if (data.ok) {
      setResult({ ok: true, msg: 'Sincronización completada.' });
    } else {
      setResult({ ok: false, msg: data.error || 'Error al sincronizar.' });
    }
  }

  const progPct = prog ? Math.round((prog.count / prog.total) * 100) : 0;

  return html`
    <div class="panel followers-grid" id="followers-panel">
      
      <!-- Columna Izquierda: Resumen -->
      <div class="followers-col">
        <div class="section">
          <div class="section-header"><span class="section-icon"><i class="fa-solid fa-chart-simple"></i></span> Resumen</div>
          <div class="section-body">
            <div class="followers-stat">
              <div class="stat-card">
                <div class="stat-value">${sync?.total ?? '—'}</div>
                <div class="stat-label">Total</div>
              </div>
              <div class="stat-card new">
                <div class="stat-value">${sync?.new_count ?? '—'}</div>
                <div class="stat-label">Nuevos</div>
              </div>
              <div class="stat-card lost">
                <div class="stat-value">${sync?.lost_count ?? '—'}</div>
                <div class="stat-label">Perdidos</div>
              </div>
            </div>

            ${prog ? html`
              <div>
                <div class="progress-text" style="margin-bottom:6px">${prog.count} / ${prog.total} seguidores</div>
                <div class="progress-bar-wrap">
                  <div class="progress-bar-fill" style="width:${progPct}%"></div>
                </div>
              </div>
            ` : null}

            <button
              id="btn-sync-followers"
              class="btn btn-primary"
              style="width:100%"
              onClick=${handleSync}
              disabled=${syncing}
            >
              ${syncing ? html`<span class="spinner"></span> Sincronizando...` : html`<i class="fa-solid fa-rotate"></i> Sincronizar ahora`}
            </button>

            ${result ? html`<div class="result-msg ${result.ok ? 'ok' : 'err'}">${result.msg}</div>` : null}
          </div>
        </div>

        ${!sync ? html`
          <div style="text-align:center;color:var(--text-muted);font-size:13px;padding:20px">
            Sin datos de sync. Presiona "Sincronizar ahora" o espera la sincronización automática al iniciar.
          </div>
        ` : null}
      </div>

      <!-- Columna Derecha: Nuevos y Perdidos -->
      <div class="followers-col">
        <!-- Nuevos seguidores -->
        ${sync?.new_labels?.length > 0 ? html`
          <div class="section">
            <div class="section-header" style="color:var(--success)"><span class="section-icon"><i class="fa-solid fa-user-plus"></i></span> Nuevos (${sync.new_count})</div>
            <div class="section-body">
              <div class="follower-list">
                ${sync.new_labels.map((l, i) => html`<div key=${i} class="follower-item new">${l}</div>`)}
              </div>
            </div>
          </div>
        ` : null}

        <!-- Perdidos -->
        ${sync?.lost_labels?.length > 0 ? html`
          <div class="section">
            <div class="section-header" style="color:var(--danger)"><span class="section-icon"><i class="fa-solid fa-user-minus"></i></span> Dejaron de seguir (${sync.lost_count})</div>
            <div class="section-body">
              <div class="follower-list">
                ${sync.lost_labels.map((l, i) => html`<div key=${i} class="follower-item lost">${l}</div>`)}
              </div>
            </div>
          </div>
        ` : null}
      </div>

    </div>
  `;
}
