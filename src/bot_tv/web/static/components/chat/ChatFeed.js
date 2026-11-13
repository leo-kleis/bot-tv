import { html, memo, useEffect, useRef, useState, useCallback } from 'preact-setup';
import { ChatMessageCont, ChatMessageGroup, ChatMessageSystem } from './ChatMessageRow.js';

/** @typedef {import('/static/lib/emotes.js').EmotesMap} EmotesMap */
/** @typedef {import('/static/state/types.js').ChatEntry} ChatEntry */
/** @typedef {import('/static/state/types.js').ChatMessage} ChatMessage */

const SCROLL_BOTTOM_THRESHOLD_PX = 60;

/**
 * Feed de mensajes del chat con auto-scroll inteligente y botón para bajar.
 *
 * @param {Object} props
 * @param {ChatEntry[]} props.displayMessages
 * @param {EmotesMap} props.emotesMap
 * @param {(msg: ChatMessage) => void} props.onUserClick
 * @param {(e: MouseEvent, msg: ChatMessage) => void} props.onMsgContext
 */
export const ChatFeed = memo(function ChatFeed({
  displayMessages,
  emotesMap,
  onUserClick,
  onMsgContext,
}) {
  /** @type {import('preact').RefObject<HTMLDivElement | null>} */
  const feedRef = useRef(null);
  const autoScrollRef = useRef(true);
  const [isAtBottom, setIsAtBottom] = useState(true);

  // Auto-scroll solo si el usuario no subió manualmente
  useEffect(() => {
    const el = feedRef.current;
    if (!el || !autoScrollRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [displayMessages]);

  const handleScroll = useCallback(() => {
    const el = feedRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_BOTTOM_THRESHOLD_PX;
    setIsAtBottom(atBottom);
    autoScrollRef.current = atBottom;
  }, []);

  const scrollToBottom = useCallback(() => {
    const el = feedRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    setIsAtBottom(true);
    autoScrollRef.current = true;
  }, []);

  return html`
    <div
      class="chat-feed-container"
      style="position:relative;flex:1;min-height:0;display:flex;flex-direction:column"
    >
      <div
        class="chat-feed"
        ref=${feedRef}
        onScroll=${handleScroll}
        id="chat-feed"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
      >
        ${
          displayMessages.length === 0
            ? html`
                <div class="chat-empty">
                  <span class="empty-icon" aria-hidden="true"
                    ><i
                      class="fa-regular fa-comments fa-3x"
                      style="color:var(--text-muted);margin-bottom:12px"
                    ></i
                  ></span>
                  <span>Esperando mensajes...</span>
                </div>
              `
            : displayMessages.map((entry, i) => {
                const msgKey = entry._uid || entry.timestamp;
                if (entry.isSystem) {
                  return html`<${ChatMessageSystem} key=${msgKey} msg=${entry} />`;
                }
                const prev = displayMessages[i - 1];
                const isGrouped =
                  prev && !prev.isSystem && prev.user_id && prev.user_id === entry.user_id;
                const rowKey = entry._uid || entry.message_id || entry.id || entry.timestamp;
                return isGrouped
                  ? html`<${ChatMessageCont}
                      key=${rowKey}
                      msg=${entry}
                      emotesMap=${emotesMap}
                      onMsgContext=${onMsgContext}
                    />`
                  : html`<${ChatMessageGroup}
                      key=${rowKey}
                      msg=${entry}
                      emotesMap=${emotesMap}
                      onUserClick=${onUserClick}
                      onMsgContext=${onMsgContext}
                    />`;
              })
        }
      </div>

      ${
        !isAtBottom && displayMessages.length > 0
          ? html`
              <button type="button" class="scroll-bottom-btn" onClick=${scrollToBottom}>
                <i class="fa-solid fa-arrow-down" aria-hidden="true"></i> Mensajes nuevos
              </button>
            `
          : null
      }
    </div>
  `;
});
