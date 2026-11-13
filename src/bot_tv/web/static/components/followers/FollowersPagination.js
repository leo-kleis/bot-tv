import { html } from 'preact-setup';
import { getPageNumbers } from './followersUtils.js';

export function FollowersPagination({ page, totalPages, totalUsers, currentCount, onPageChange }) {
  if (totalPages <= 1) return null;

  return html`
    <nav class="pagination-bar" aria-label="Paginación de usuarios">
      <div class="pagination-info">
        Mostrando ${currentCount} usuarios de ${totalUsers} encontrados
      </div>
      <div class="pagination-buttons">
        <button
          type="button"
          class="btn btn-secondary btn-sm btn-icon"
          onClick=${() => onPageChange(Math.max(1, page - 1))}
          disabled=${page === 1}
          aria-label="Página anterior"
        >
          <i class="fa-solid fa-chevron-left"></i> Anterior
        </button>
        <span class="pagination-pages">
          ${getPageNumbers(page, totalPages).map((p, i) => {
            if (p === '...') {
              return html`<span key=${i} class="pagination-ellipsis">...</span>`;
            }
            return html`
              <button
                key=${i}
                type="button"
                class="btn btn-sm ${page === p ? 'btn-primary' : 'btn-secondary'}"
                style="min-width: 32px; padding: 6px 4px;"
                onClick=${() => onPageChange(p)}
                aria-label="Página ${p}"
                aria-current=${page === p ? 'page' : undefined}
              >
                ${p}
              </button>
            `;
          })}
        </span>
        <button
          type="button"
          class="btn btn-secondary btn-sm btn-icon"
          onClick=${() => onPageChange(Math.min(totalPages, page + 1))}
          disabled=${page === totalPages}
          aria-label="Página siguiente"
        >
          Siguiente <i class="fa-solid fa-chevron-right"></i>
        </button>
      </div>
    </nav>
  `;
}
