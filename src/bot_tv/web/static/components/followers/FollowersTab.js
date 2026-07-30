import { html, useState, useEffect, useRef } from 'preact-setup';
import { apiPost, apiGet } from '/static/components/api.js';
import { FollowersSummary } from './FollowersSummary.js';
import { FollowersFilterBar } from './FollowersFilterBar.js';
import { FollowersTable } from './FollowersTable.js';
import { FollowersPagination } from './FollowersPagination.js';
import { UserRolesModal } from './UserRolesModal.js';
import { UserHistoryDrawer } from '/static/components/followers/UserHistoryDrawer.js';

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

  // Estados de paginación y carga
  const [users, setUsers] = useState([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [page, setPage] = useState(1);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(null);
  const [selectedUserForRoles, setSelectedUserForRoles] = useState(null);
  const [historyUser, setHistoryUser] = useState(null);
  const [tempRoles, setTempRoles] = useState({
    is_bot: false,
    is_moderator: false,
    is_vip: false,
    is_subscriber: false,
  });

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

  // Control de carga al cambiar filtros o paginar
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

  // Limpiar campos de fecha del filtro opuesto al cambiar el combo de estado
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

  async function openRolesModal(u) {
    setActionInProgress(u.username);
    const res = await apiPost('/api/sync_user_roles', {
      username: u.username,
    });
    setActionInProgress(null);
    if (res && res.ok && res.data) {
      setSelectedUserForRoles(u);
      setTempRoles({
        is_bot: !!res.data.is_bot,
        is_moderator: !!res.data.is_moderator,
        is_vip: !!res.data.is_vip,
        is_subscriber: !!res.data.is_subscriber,
      });
      fetchUsers();
    } else {
      window.alert(
        res
          ? res.error || 'Error al sincronizar roles con Twitch.'
          : 'Error al sincronizar roles con Twitch.'
      );
    }
  }

  async function handleSaveRoles() {
    if (!selectedUserForRoles) return;
    setActionInProgress(selectedUserForRoles.username);
    const res = await apiPost('/api/update_user_roles', {
      username: selectedUserForRoles.username,
      is_bot: tempRoles.is_bot,
      is_moderator: tempRoles.is_moderator,
      is_vip: tempRoles.is_vip,
    });
    setActionInProgress(null);
    setSelectedUserForRoles(null);
    if (res && res.ok) {
      fetchUsers();
    } else {
      window.alert(res.error || 'Error al actualizar los roles.');
    }
  }

  async function handleSetNickname(u) {
    const msg = `Introduce el apodo para ${u.display_name || u.username} (deja en blanco para eliminarlo):`;
    const newNick = window.prompt(msg, u.nickname || '');
    if (newNick === null) return;

    setActionInProgress(u.username);
    const res = await apiPost('/api/set_nickname', {
      username: u.username,
      nickname: newNick.trim() || null,
    });
    setActionInProgress(null);
    if (res && res.ok) {
      fetchUsers();
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
    <div class="panel" id="followers-panel" style="display:flex; flex-direction:column; gap:24px;">
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

        <div class="section-body" style="gap:16px;">
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
              actionInProgress=${actionInProgress}
              onSort=${handleSort}
              onOpenRoles=${openRolesModal}
              onSetNickname=${handleSetNickname}
              onOpenHistory=${u => setHistoryUser(u)}
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

      <!-- Modal de Roles -->
      <${UserRolesModal}
        user=${selectedUserForRoles}
        tempRoles=${tempRoles}
        setTempRoles=${setTempRoles}
        onClose=${() => setSelectedUserForRoles(null)}
        onSave=${handleSaveRoles}
      />
    </div>

    <!-- Drawer de Historial -->
    ${
      historyUser
        ? html`<${UserHistoryDrawer} user=${historyUser} onClose=${() => setHistoryUser(null)} />`
        : null
    }
  `;
}
