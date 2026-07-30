import { html } from 'preact-setup';
import { getPageNumbers } from './followersUtils.js';

export function FollowersPagination({ page, totalPages, totalUsers, currentCount, onPageChange }) {
  if (totalPages <= 1) return null;

  return html`
    <div class="pagination-bar">
      <div class="pagination-info">
        Mostrando ${currentCount} usuarios de ${totalUsers} encontrados
      </div>
      <div class="pagination-buttons">
        <button
          class="btn btn-secondary btn-sm btn-icon"
          onClick=${() => onPageChange(Math.max(1, page - 1))}
          disabled=${page === 1}
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
                class="btn btn-sm ${page === p ? 'btn-primary' : 'btn-secondary'}"
                style="min-width: 32px; padding: 6px 4px;"
                onClick=${() => onPageChange(p)}
              >
                ${p}
              </button>
            `;
          })}
        </span>
        <button
          class="btn btn-secondary btn-sm btn-icon"
          onClick=${() => onPageChange(Math.min(totalPages, page + 1))}
          disabled=${page === totalPages}
        >
          Siguiente <i class="fa-solid fa-chevron-right"></i>
        </button>
      </div>
    </div>
  `;
}
