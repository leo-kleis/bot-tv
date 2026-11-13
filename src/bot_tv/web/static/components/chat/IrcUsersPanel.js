import { html, memo, useEffect, useMemo, useRef, useState } from 'preact-setup';
import { toRgb, fmtTime } from 'lib/utils';
import { UserAvatar } from '../UserAvatar.js';
import { getFocusableElements, trapFocus, setupInertIsolation } from '/static/lib/a11y.js';

/** @typedef {import('/static/state/types.js').IrcUser} IrcUser */
/** @typedef {import('/static/state/types.js').IrcUsersMap} IrcUsersMap */

const IRC_DRAWER_MEDIA_QUERY = '(max-width: 1024px) and (min-height: 481px), (max-height: 480px)';

/**
 * Fila de usuario en la lista lateral de IRC.
 */
const IrcUserRow = memo(function IrcUserRow({ user, onUserClick }) {
  const color = toRgb(user.color_rgb);
  const timeStr = user.timestamp ? fmtTime(user.timestamp) : '--:--';
  const nameStr = user.display_name || user.username || 'usuario';
  const isParted = user.present === false;

  let followStatus = '';
  if (user.role === 'Broadcaster') {
    followStatus = '[Broadcaster]';
  } else if (user.role === 'Bot' || user.is_bot) {
    followStatus = '[Bot]';
  } else if (user.role && user.role !== 'Visita' && user.role !== 'Desconocido') {
    followStatus = `[${user.role}]`;
  } else {
    followStatus = '[Visita]';
  }

  const badges = [];
  if (user.is_moderator) {
    badges.push(html`<span class="irc-badge badge-moderator">Mod</span>`);
  }
  if (user.is_vip) {
    badges.push(html`<span class="irc-badge badge-vip">VIP</span>`);
  }
  if (user.is_subscriber) {
    const label =
      user.sub_tier === '3000' ? 'Sub T3' : user.sub_tier === '2000' ? 'Sub T2' : 'Sub T1';
    badges.push(html`<span class="irc-badge badge-subscriber">${label}</span>`);
  }

  const metaText = user.nickname ? `${user.nickname} · ${followStatus}` : followStatus;

  return html`
    <div
      class="irc-user ${isParted ? 'is-parted' : ''}"
      role="button"
      tabindex=${0}
      aria-label=${`Ver perfil de ${nameStr}`}
      onClick=${() => onUserClick(user)}
      onKeyDown=${
        /** @param {KeyboardEvent} e */ e => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onUserClick(user);
          }
        }
      }
      style="cursor:pointer;"
    >
      <${UserAvatar} userId=${user.user_id} displayName=${nameStr} color=${color} size="md" />
      <div class="irc-user-details">
        <div class="irc-user-top">
          <span class="irc-name" style="color:${color}">${nameStr}</span>
          ${badges.length > 0 ? html`<div class="irc-user-badges">${badges}</div>` : null}
        </div>
        <div class="irc-user-bottom">
          <span class="irc-meta">${metaText}</span>
          <span class="irc-time">${timeStr}</span>
        </div>
      </div>
    </div>
  `;
});

/**
 * Panel lateral de usuarios conectados al canal IRC (inline en desktop, drawer aislado en móvil/tablet).
 *
 * @param {Object} props
 * @param {IrcUsersMap} props.ircUsers
 * @param {boolean} props.ircConnected
 * @param {boolean} props.showIrcMobile
 * @param {(open: boolean) => void} props.onToggleIrc
 * @param {(user: IrcUser) => void} props.onUserClick
 */
export const IrcUsersPanel = memo(function IrcUsersPanel({
  ircUsers,
  ircConnected,
  showIrcMobile,
  onToggleIrc,
  onUserClick,
}) {
  /** @type {import('preact').RefObject<HTMLElement | null>} */
  const ircPanelRef = useRef(null);
  /** @type {import('preact').RefObject<Element | null>} */
  const ircTriggerRef = useRef(null);
  const onToggleIrcRef = useRef(onToggleIrc);
  onToggleIrcRef.current = onToggleIrc;

  const [isDrawerMode, setIsDrawerMode] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia(IRC_DRAWER_MEDIA_QUERY).matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia(IRC_DRAWER_MEDIA_QUERY);
    setIsDrawerMode(mq.matches);
    /** @param {MediaQueryListEvent} e */
    const handleChange = e => setIsDrawerMode(e.matches);
    mq.addEventListener('change', handleChange);
    return () => mq.removeEventListener('change', handleChange);
  }, []);

  // Evitar que el drawer IRC cerrado fuera de pantalla sea alcanzable con Tab
  useEffect(() => {
    const panelEl = ircPanelRef.current;
    if (!panelEl) return;
    if (isDrawerMode && !showIrcMobile) {
      panelEl.setAttribute('inert', '');
    } else {
      panelEl.removeAttribute('inert');
    }
  }, [isDrawerMode, showIrcMobile]);

  // Aislamiento inert, foco inicial y restauración al cerrar en modo drawer
  useEffect(() => {
    if (!showIrcMobile) return;

    ircTriggerRef.current = document.activeElement;
    const panelEl = ircPanelRef.current;
    if (panelEl) {
      panelEl.removeAttribute('inert');
    }
    const restoreInert = setupInertIsolation(panelEl);

    const focusTimer = requestAnimationFrame(() => {
      if (ircPanelRef.current) {
        const first = getFocusableElements(ircPanelRef.current)[0];
        if (first) {
          first.focus();
        } else {
          ircPanelRef.current.focus();
        }
      }
    });

    /** @param {KeyboardEvent} e */
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        onToggleIrcRef.current(false);
        return;
      }
      if (e.key === 'Tab') {
        trapFocus(ircPanelRef.current, e);
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      cancelAnimationFrame(focusTimer);
      window.removeEventListener('keydown', handleKeyDown);
      restoreInert();
      const prevEl = ircTriggerRef.current;
      if (prevEl instanceof HTMLElement && document.body.contains(prevEl)) {
        prevEl.focus();
      }
    };
  }, [showIrcMobile]);

  const users = useMemo(() => {
    return [...ircUsers.values()]
      .filter(u => u.role !== 'Broadcaster' && !u.is_bot && u.role !== 'Bot')
      .sort((a, b) => {
        const aPresent = a.present !== false;
        const bPresent = b.present !== false;

        if (aPresent !== bPresent) {
          return aPresent ? -1 : 1;
        }

        if (aPresent && bPresent) {
          const aTime = a.joinedAt || a.timestamp || '';
          const bTime = b.joinedAt || b.timestamp || '';
          return aTime.localeCompare(bTime);
        }

        const aPartTime = a.partedAt || a.timestamp || '';
        const bPartTime = b.partedAt || b.timestamp || '';
        return bPartTime.localeCompare(aPartTime);
      });
  }, [ircUsers]);

  return html`
    ${
      showIrcMobile
        ? html`
            <div
              class="irc-overlay-mobile"
              aria-hidden="true"
              onClick=${() => onToggleIrc(false)}
            ></div>
          `
        : null
    }

    <aside
      class="irc-panel"
      ref=${ircPanelRef}
      tabIndex=${showIrcMobile ? -1 : undefined}
      role=${showIrcMobile ? 'dialog' : undefined}
      aria-modal=${showIrcMobile ? 'true' : undefined}
      aria-labelledby=${showIrcMobile ? 'irc-panel-title' : undefined}
      aria-label=${showIrcMobile ? undefined : 'Usuarios en el canal'}
    >
      <div class="irc-panel-header">
        <span id="irc-panel-title">En canal</span>
        <div style="display:flex;align-items:center;gap:6px;">
          ${
            !ircConnected &&
            html`
              <span class="irc-status-warning" title="IRC Desconectado (Reintentando...)">
                <i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>
              </span>
            `
          }
          ${
            showIrcMobile
              ? html`
                  <button
                    type="button"
                    class="history-header-close"
                    style="width:24px;height:24px;font-size:12px;"
                    aria-label="Cerrar panel de usuarios"
                    onClick=${() => onToggleIrc(false)}
                  >
                    <i class="fa-solid fa-xmark" aria-hidden="true"></i>
                  </button>
                `
              : null
          }
        </div>
      </div>

      <div class="irc-feed" id="irc-feed">
        ${
          !ircConnected &&
          html`
            <div class="irc-disconnect-alert">
              <span class="alert-icon" aria-hidden="true"
                ><i class="fa-solid fa-triangle-exclamation"></i
              ></span>
              <span class="alert-title">IRC Desconectado</span>
              <span class="alert-desc">Intentando reconectar automáticamente...</span>
            </div>
          `
        }
        ${
          users.length === 0
            ? !ircConnected
              ? null
              : html`
                  <div
                    style="padding:16px 10px;color:var(--text-muted);font-size:11px;text-align:center"
                  >
                    Vacío
                  </div>
                `
            : users.map(
                u => html`
                  <${IrcUserRow}
                    key=${u.user_id || u.username}
                    user=${u}
                    onUserClick=${onUserClick}
                  />
                `
              )
        }
      </div>
    </aside>
  `;
});
