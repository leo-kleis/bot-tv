export function formatDate(isoString) {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString('es-ES', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

export function getPageNumbers(current, total) {
  const pages = [];
  const maxVisible = 5;

  if (total <= maxVisible) {
    for (let i = 1; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);

    let start = Math.max(2, current - 1);
    let end = Math.min(total - 1, current + 1);

    if (current <= 3) {
      end = 4;
    } else if (current >= total - 2) {
      start = total - 3;
    }

    if (start > 2) {
      pages.push('...');
    }

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (end < total - 1) {
      pages.push('...');
    }

    pages.push(total);
  }
  return pages;
}

export function getTodayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export const SELECT_OPTIONS = [
  { value: 'all', label: 'Todos los usuarios' },
  { value: 'follower', label: 'Seguidor' },
  { value: 'not_follower', label: 'No Seguidor' },
  { value: 'unfollower', label: 'Dejó de Seguir' },
];

export const ROLE_OPTIONS = [
  { value: 'all', label: 'Todos los roles' },
  { value: 'moderator', label: 'Moderador' },
  { value: 'vip', label: 'VIP' },
  { value: 'subscriber', label: 'Suscriptor' },
  { value: 'bot', label: 'Bot' },
];

export const HISTORY_OPTIONS = [
  { value: 'all', label: 'Todos' },
  { value: 'with_history', label: 'Con historial' },
  { value: 'no_history', label: 'Sin historial' },
];
