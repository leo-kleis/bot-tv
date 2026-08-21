import { html, useState, useEffect, useRef } from 'preact-setup';
import { apiPost, apiGet } from '/static/components/api.js';
import { FollowersSummary } from './FollowersSummary.js';
import { FollowersFilterBar } from './FollowersFilterBar.js';
import { FollowersTable } from './FollowersTable.js';
import { FollowersPagination } from './FollowersPagination.js';
import { UserProfileDrawer } from '/static/components/user/UserProfileDrawer.js';

export function FollowersTab({ followers }) {
  const allNewLabels = followers.allNewLabels || [];
  const allLostLabels = followers.allLostLabels || [];
  const [syncing, setSyncing] = useState(false);
  const [result, setResult] = useState(null);

  // Estados para filtros de listado de usuarios
  const [nameInput, setNameInput] = useState('');
  const [nameSearch, setNameSearch] = useState('');
  const [isFollower, setIsFollower] = useState('all');
  const [role, setRole] = useState('all');
  const [hasHistory, setHasHistory] = useState('all');
  const [followedAfter, setFollowedAfter] = useState('');
  const [followedBefore, setFollowedBefore] = useState('');
  const [unfollowedAfter, setUnfollowedAfter] = useState('');
  const [unfollowedBefore, setUnfollowedBefore] = useState('');

  // Estados de ordenamiento
  const [sortBy, setSortBy] = useState('username');
  const [sortOrder, setSortOrder] = useState('asc');

  // Estados de paginación, carga y perfil de usuario
  const [users, setUsers] = useState([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [page, setPage] = useState(1);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [selectedUserForProfile, setSelectedUserForProfile] = useState(null);

  const limit = 50;
  const sync = followers.lastSync;
  const prog = followers.progress;

  // Ref para almacenar filtros anteriores y prevenir doble fetch
  const prevFilters = useRef({
    nameSearch,
    isFollower,
    role,
    hasHistory,
    followedAfter,
    followedBefore,
    unfollowedAfter,
    unfollowedBefore,
    sortBy,
    sortOrder,
  });

  // Debounce del buscador de nombre (1s)
  useEffect(() => {
    const timer = setTimeout(() => {
      setNameSearch(nameInput);
    }, 1000);
    return () => clearTimeout(timer);
  }, [nameInput]);

  useEffect(() => {
    const filtersChanged =
      prevFilters.current.nameSearch !== nameSearch ||
      prevFilters.current.isFollower !== isFollower ||
      prevFilters.current.role !== role ||
      prevFilters.current.hasHistory !== hasHistory ||
      prevFilters.current.followedAfter !== followedAfter ||
      prevFilters.current.followedBefore !== followedBefore ||
      prevFilters.current.unfollowedAfter !== unfollowedAfter ||
      prevFilters.current.unfollowedBefore !== unfollowedBefore ||
      prevFilters.current.sortBy !== sortBy ||
      prevFilters.current.sortOrder !== sortOrder;

    prevFilters.current = {
      nameSearch,
      isFollower,
      role,
      hasHistory,
      followedAfter,
      followedBefore,
      unfollowedAfter,
      unfollowedBefore,
      sortBy,
      sortOrder,
    };

    if (filtersChanged && page !== 1) {
      setPage(1);
    } else {
      fetchUsers();
    }
  }, [
    page,
    nameSearch,
    isFollower,
    role,
    hasHistory,
    followedAfter,
    followedBefore,
    unfollowedAfter,
    unfollowedBefore,
    sortBy,
    sortOrder,
  ]);

  useEffect(() => {
    if (isFollower === 'follower') {
      setUnfollowedAfter('');
      setUnfollowedBefore('');
    } else if (isFollower === 'unfollower') {
      setFollowedAfter('');
      setFollowedBefore('');
    } else if (isFollower === 'not_follower') {
      setFollowedAfter('');
      setFollowedBefore('');
      setUnfollowedAfter('');
      setUnfollowedBefore('');
    }
  }, [isFollower]);

  async function fetchUsers() {
    setLoadingUsers(true);
    const params = new window.URLSearchParams();
    if (nameSearch.trim()) params.append('name', nameSearch.trim());
    if (isFollower !== 'all') params.append('is_follower', isFollower);
    if (role !== 'all') params.append('role', role);
    if (hasHistory !== 'all') params.append('has_history', hasHistory);
    if (followedAfter) params.append('followed_after', followedAfter);
    if (followedBefore) params.append('followed_before', followedBefore);
    if (unfollowedAfter) params.append('unfollowed_after', unfollowedAfter);
    if (unfollowedBefore) params.append('unfollowed_before', unfollowedBefore);
    if (sortBy) params.append('sort_by', sortBy);
    if (sortOrder) params.append('sort_order', sortOrder);
    params.append('limit', limit.toString());
    params.append('page', page.toString());

    const res = await apiGet(`/api/users?${params.toString()}`);
    setLoadingUsers(false);
    if (res && res.ok && res.data) {
      setUsers(res.data.users || []);
      setTotalUsers(res.data.total || 0);
    } else {
      setUsers([]);
      setTotalUsers(0);
    }
  }

  function handleSort(field) {
    if (sortBy === field) {
      setSortOrder(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  }

  async function handleSync() {
    setSyncing(true);
    setResult(null);
    const data = await apiPost('/api/sync_followers', {});
    setSyncing(false);
    if (data.ok) {
      setResult({ ok: true, msg: 'Sincronización completada.' });
      fetchUsers();
      setTimeout(() => {
        setResult(null);
      }, 5000);
    } else {
      setResult({ ok: false, msg: data.error || 'Error al sincronizar.' });
    }
  }

  function handleClearFilters() {
    setNameInput('');
    setNameSearch('');
    setIsFollower('all');
    setRole('all');
    setHasHistory('all');
    setFollowedAfter('');
    setFollowedBefore('');
    setUnfollowedAfter('');
    setUnfollowedBefore('');
    setSortBy('username');
    setSortOrder('asc');
    setPage(1);
  }

  const totalPages = Math.ceil(totalUsers / limit);

  return html`
    <div class="panel" id="followers-panel">
      <!-- Resumen y Sincronización -->
      <${FollowersSummary}
        sync=${sync}
        prog=${prog}
        syncing=${syncing}
        allNewLabels=${allNewLabels}
        allLostLabels=${allLostLabels}
        result=${result}
        onSync=${handleSync}
      />

      <!-- Listado de Usuarios con Filtros Avanzados -->
      <div class="section" style="border-top: 1px solid var(--border-2); padding-top: 24px;">
        <div
          class="section-header"
          style="display:flex; justify-content:space-between; align-items:center;"
        >
          <div>
            <span class="section-icon"><i class="fa-solid fa-users"></i></span> Buscador de Usuarios
            y Seguidores
          </div>
          ${
            !loadingUsers && totalUsers > 0
              ? html`
                  <span style="font-size: 12px; color: var(--text-muted); font-weight: normal;">
                    Total:
                    <strong style="color: var(--accent-text);">${totalUsers}</strong> usuarios
                    encontrados
                  </span>
                `
              : null
          }
        </div>

        <div class="section-body">
          <!-- Barra de Filtros -->
          <${FollowersFilterBar}
            nameInput=${nameInput}
            setNameInput=${setNameInput}
            isFollower=${isFollower}
            setIsFollower=${setIsFollower}
            role=${role}
            setRole=${setRole}
            hasHistory=${hasHistory}
            setHasHistory=${setHasHistory}
            followedAfter=${followedAfter}
            setFollowedAfter=${setFollowedAfter}
            followedBefore=${followedBefore}
            setFollowedBefore=${setFollowedBefore}
            unfollowedAfter=${unfollowedAfter}
            setUnfollowedAfter=${setUnfollowedAfter}
            unfollowedBefore=${unfollowedBefore}
            setUnfollowedBefore=${setUnfollowedBefore}
            onClearFilters=${handleClearFilters}
          />

          <!-- Tabla de Resultados y Paginación -->
          <div>
            <${FollowersTable}
              users=${users}
              loadingUsers=${loadingUsers}
              sortBy=${sortBy}
              sortOrder=${sortOrder}
              onSort=${handleSort}
              onOpenProfile=${u => setSelectedUserForProfile(u)}
            />

            <${FollowersPagination}
              page=${page}
              totalPages=${totalPages}
              totalUsers=${totalUsers}
              currentCount=${users.length}
              onPageChange=${setPage}
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Drawer Unificado de Perfil de Usuario -->
    ${
      selectedUserForProfile
        ? html`
            <${UserProfileDrawer}
              user=${selectedUserForProfile}
              onClose=${() => {
                setSelectedUserForProfile(null);
                fetchUsers();
              }}
            />
          `
        : null
    }
  `;
}
