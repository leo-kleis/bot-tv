import { html } from 'preact-setup';
import { CustomSelect } from '/static/components/CustomSelect.js';
import { SELECT_OPTIONS, ROLE_OPTIONS, HISTORY_OPTIONS, getTodayStr } from './followersUtils.js';

export function FollowersFilterBar({
  nameInput,
  setNameInput,
  isFollower,
  setIsFollower,
  role,
  setRole,
  hasHistory,
  setHasHistory,
  followedAfter,
  setFollowedAfter,
  followedBefore,
  setFollowedBefore,
  unfollowedAfter,
  setUnfollowedAfter,
  unfollowedBefore,
  setUnfollowedBefore,
  onClearFilters,
}) {
  return html`
    <div class="filters-bar">
      <!-- Buscar por Nombre -->
      <div class="filter-group">
        <label class="filter-label">Nombre / Apodo</label>
        <input
          type="text"
          placeholder="Buscar usuario..."
          value=${nameInput}
          onInput=${e => setNameInput(e.target.value)}
        />
      </div>

      <!-- Estado de Seguidor -->
      <div class="filter-group">
        <label class="filter-label">Estado Seguimiento</label>
        <${CustomSelect} value=${isFollower} onChange=${setIsFollower} options=${SELECT_OPTIONS} />
      </div>

      <!-- Rol -->
      <div class="filter-group">
        <label class="filter-label">Rol</label>
        <${CustomSelect} value=${role} onChange=${setRole} options=${ROLE_OPTIONS} />
      </div>

      <!-- Historial de Chat -->
      <div class="filter-group">
        <label class="filter-label">Historial Chat</label>
        <${CustomSelect} value=${hasHistory} onChange=${setHasHistory} options=${HISTORY_OPTIONS} />
      </div>

      <!-- Rango Fecha Seguimiento -->
      <div class="filter-group">
        <label class="filter-label">Seguidor desde</label>
        <div class="filter-dates-row">
          <input
            type="date"
            value=${followedAfter}
            onChange=${e => {
              const val = e.target.value;
              setFollowedAfter(val);
              if (val) {
                setIsFollower('follower');
                if (!followedBefore) {
                  setFollowedBefore(getTodayStr());
                }
              }
            }}
            placeholder="Desde"
            disabled=${isFollower === 'not_follower' || isFollower === 'unfollower'}
            max=${followedBefore || ''}
          />
          <span class="filter-separator">a</span>
          <input
            type="date"
            value=${followedBefore}
            onChange=${e => {
              const val = e.target.value;
              setFollowedBefore(val);
              if (val) {
                setIsFollower('follower');
                if (!followedAfter) {
                  setFollowedAfter(val);
                }
              }
            }}
            placeholder="Hasta"
            disabled=${isFollower === 'not_follower' || isFollower === 'unfollower'}
            min=${followedAfter || ''}
          />
        </div>
      </div>

      <!-- Rango Fecha Unfollow -->
      <div class="filter-group">
        <label class="filter-label">Dejó de seguir</label>
        <div class="filter-dates-row">
          <input
            type="date"
            value=${unfollowedAfter}
            onChange=${e => {
              const val = e.target.value;
              setUnfollowedAfter(val);
              if (val) {
                setIsFollower('unfollower');
                if (!unfollowedBefore) {
                  setUnfollowedBefore(getTodayStr());
                }
              }
            }}
            placeholder="Desde"
            disabled=${isFollower === 'follower' || isFollower === 'not_follower'}
            max=${unfollowedBefore || ''}
          />
          <span class="filter-separator">a</span>
          <input
            type="date"
            value=${unfollowedBefore}
            onChange=${e => {
              const val = e.target.value;
              setUnfollowedBefore(val);
              if (val) {
                setIsFollower('unfollower');
                if (!unfollowedAfter) {
                  setUnfollowedAfter(val);
                }
              }
            }}
            placeholder="Hasta"
            disabled=${isFollower === 'follower' || isFollower === 'not_follower'}
            min=${unfollowedAfter || ''}
          />
        </div>
      </div>

      <!-- Botón Limpiar -->
      <div class="filter-group filter-group-actions">
        <button
          class="btn btn-secondary btn-icon"
          onClick=${onClearFilters}
          title="Limpiar filtros"
        >
          <i class="fa-solid fa-filter-circle-xmark"></i> Limpiar
        </button>
      </div>
    </div>
  `;
}
