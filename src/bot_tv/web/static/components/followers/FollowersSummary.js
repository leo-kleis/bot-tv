import { html } from 'preact-setup';

export function FollowersSummary({
  sync,
  prog,
  syncing,
  allNewLabels = [],
  allLostLabels = [],
  result,
  onSync,
}) {
  const progPct = prog && prog.total > 0 ? Math.round((prog.count / prog.total) * 100) : 0;

  return html`
    <div class="two-col-grid">
      <!-- Columna Izquierda: Resumen y Sincronizador -->
      <div class="two-col">
        <div class="section">
          <div class="section-header">
            <span class="section-icon"><i class="fa-solid fa-chart-simple"></i></span> Resumen
          </div>
          <div class="section-body">
            <div class="followers-stat">
              <div class="stat-card">
                <div class="stat-value">${sync?.total ?? '—'}</div>
                <div class="stat-label">Total</div>
              </div>
              <div class="stat-card new">
                <div class="stat-value">${allNewLabels.length || '—'}</div>
                <div class="stat-label">Nuevos</div>
              </div>
              <div class="stat-card lost">
                <div class="stat-value">${allLostLabels.length || '—'}</div>
                <div class="stat-label">Perdidos</div>
              </div>
            </div>

            ${
              prog
                ? html`
                    <div>
                      <div class="progress-text" style="margin-bottom:6px">
                        ${
                          prog.total > 0
                            ? `${prog.count} / ${prog.total} seguidores`
                            : 'Iniciando sincronización...'
                        }
                      </div>
                      <div class="progress-bar-wrap">
                        <div class="progress-bar-fill" style="width:${progPct}%"></div>
                      </div>
                    </div>
                  `
                : null
            }

            <button
              id="btn-sync-followers"
              class="btn btn-primary"
              style="width:100%"
              onClick=${onSync}
              disabled=${syncing || !!prog || !sync}
            >
              ${
                syncing || !!prog
                  ? html`<span class="spinner"></span> Sincronizando...`
                  : !sync
                    ? html`<span class="spinner"></span> Inicializando bot...`
                    : html`<i class="fa-solid fa-rotate"></i> Sincronizar ahora`
              }
            </button>

            ${
              result
                ? html`<div class="result-msg ${result.ok ? 'ok' : 'err'}">${result.msg}</div>`
                : null
            }
          </div>
        </div>

        ${
          !sync
            ? html`
                <div style="text-align:center;color:var(--text-muted);font-size:13px;padding:20px">
                  Sin datos de sync. Presiona "Sincronizar ahora" o espera la sincronización
                  automática al iniciar.
                </div>
              `
            : null
        }
      </div>

      <!-- Columna Derecha: Nuevos y Perdidos acumulados en la sesión -->
      ${
        allNewLabels.length > 0 || allLostLabels.length > 0
          ? html`
              <div class="two-col">
                <!-- Nuevos seguidores -->
                ${
                  allNewLabels.length > 0
                    ? html`
                        <div class="section">
                          <div class="section-header" style="color:var(--success)">
                            <span class="section-icon"><i class="fa-solid fa-user-plus"></i></span>
                            Nuevos (${allNewLabels.length})
                          </div>
                          <div class="section-body">
                            <div class="follower-list">
                              ${allNewLabels.map(
                                (l, i) => html`<div key=${i} class="follower-item new">${l}</div>`
                              )}
                            </div>
                          </div>
                        </div>
                      `
                    : null
                }

                <!-- Perdidos -->
                ${
                  allLostLabels.length > 0
                    ? html`
                        <div class="section">
                          <div class="section-header" style="color:var(--danger)">
                            <span class="section-icon"><i class="fa-solid fa-user-minus"></i></span>
                            Dejaron de seguir (${allLostLabels.length})
                          </div>
                          <div class="section-body">
                            <div class="follower-list">
                              ${allLostLabels.map(
                                (l, i) => html`<div key=${i} class="follower-item lost">${l}</div>`
                              )}
                            </div>
                          </div>
                        </div>
                      `
                    : null
                }
              </div>
            `
          : null
      }
    </div>
  `;
}
