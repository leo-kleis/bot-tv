import { html, memo, useCallback, useEffect, useMemo, useRef, useState } from 'preact-setup';
import { apiPost } from '../api.js';
import { ComposerBar } from '../ComposerBar.js';

/** @typedef {import('/static/state/types.js').AppDispatch} AppDispatch */

const FOCUS_RESTORE_DELAY_MS = 50;
const TWITCH_MESSAGE_MAX_LENGTH = 500;

/**
 * @typedef {Object} ChatAccount
 * @property {string} user_id
 * @property {string} username
 * @property {'bot' | 'broadcaster' | string} type
 */

/**
 * Barra fija inferior para redactar y enviar mensajes al chat de Twitch.
 *
 * @param {Object} props
 * @param {ChatAccount[]} props.accounts
 * @param {string} props.selectedSenderId
 * @param {(senderId: string) => void} props.onSelectSender
 * @param {AppDispatch} props.dispatch
 */
export const ChatInputBar = memo(function ChatInputBar({
  accounts,
  selectedSenderId,
  onSelectSender,
  dispatch,
}) {
  const [inputText, setInputText] = useState('');
  const [sendingMsg, setSendingMsg] = useState(false);
  /** @type {import('preact').RefObject<HTMLTextAreaElement | null>} */
  const inputRef = useRef(null);
  /** @type {import('preact').RefObject<ReturnType<typeof setTimeout> | null>} */
  const focusTimerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (focusTimerRef.current !== null) {
        clearTimeout(focusTimerRef.current);
        focusTimerRef.current = null;
      }
    };
  }, []);

  const accountOptions = useMemo(
    () =>
      accounts.map(acc => ({
        value: acc.user_id,
        label: `${acc.username} (${acc.type === 'bot' ? 'Bot' : 'Broadcaster'})`,
      })),
    [accounts]
  );

  /** @param {string} nextValue */
  const handleInputChange = useCallback(nextValue => {
    setInputText(nextValue.replace(/[\r\n]+/g, ' '));
  }, []);

  /** @param {Event} [e] */
  const handleSend = useCallback(
    async e => {
      if (e) e.preventDefault();
      if (!inputText.trim() || !selectedSenderId || sendingMsg) return;

      setSendingMsg(true);
      const messageText = inputText;

      const res = await apiPost('/api/send_chat_message', {
        sender_id: selectedSenderId,
        message: messageText,
      });

      setSendingMsg(false);

      if (res.ok) {
        setInputText('');
      } else if (dispatch) {
        const toastId = Date.now().toString() + Math.random().toString(36).slice(2, 11);
        dispatch({
          type: 'ADD_TOAST',
          toast: {
            id: toastId,
            type: 'api_error',
            data: { message: `No se pudo enviar: ${res.error || 'error desconocido'}` },
          },
        });
      }

      if (focusTimerRef.current !== null) {
        clearTimeout(focusTimerRef.current);
      }
      focusTimerRef.current = setTimeout(() => {
        focusTimerRef.current = null;
        inputRef.current?.focus();
      }, FOCUS_RESTORE_DELAY_MS);
    },
    [inputText, selectedSenderId, sendingMsg, dispatch]
  );

  const senderPrefix = useMemo(
    () => html`<i class="fa-solid fa-user-circle" aria-hidden="true"></i>`,
    []
  );

  const counterMeta =
    inputText.length > 0
      ? html`<span class="composer-rpm-badge"
          >${inputText.length}/${TWITCH_MESSAGE_MAX_LENGTH}</span
        >`
      : null;

  return html`
    <${ComposerBar}
      className="chat-composer"
      inputId="chat-composer-input"
      submitId="chat-composer-send"
      inputRef=${inputRef}
      value=${inputText}
      onChange=${handleInputChange}
      onSubmit=${handleSend}
      multiline=${false}
      maxLength=${TWITCH_MESSAGE_MAX_LENGTH}
      placeholder="Escribe un mensaje al chat..."
      ariaLabel="Escribe un mensaje al chat"
      submitAriaLabel="Enviar mensaje"
      disabled=${sendingMsg}
      sending=${sendingMsg}
      sendDisabled=${!inputText.trim() || sendingMsg || !selectedSenderId}
      selectId="chat-sender-select"
      selectOptions=${accountOptions}
      selectValue=${selectedSenderId}
      onSelectChange=${onSelectSender}
      selectAriaLabel="Cuenta para enviar mensaje"
      selectDisabled=${sendingMsg}
      selectTriggerPrefix=${senderPrefix}
      metaContent=${counterMeta}
    />
  `;
});
