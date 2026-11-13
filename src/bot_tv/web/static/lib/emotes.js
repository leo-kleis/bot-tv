import { html } from 'preact-setup';
import { sanitizeHttpUrl } from 'lib/utils';

const TWITCH_EMOTE_CDN = 'https://static-cdn.jtvnw.net/emoticons/v2';

/**
 * @typedef {Object} EmoteEntry
 * @property {string} url
 * @property {'bttv' | 'ffz'} provider
 */

/** @typedef {Record<string, EmoteEntry>} EmotesMap */

/**
 * @typedef {Object} TwitchEmote
 * @property {string} id
 * @property {string} text
 */

/**
 * @typedef {Object} FfzEmoticon
 * @property {string} name
 * @property {Record<string, string>} [urls]
 */

/**
 * @typedef {Object} BttvEmote
 * @property {string} id
 * @property {string} code
 */

/** @type {EmotesMap | null} */
let cachedEmotes = null;
/** @type {string | null} */
let cachedBroadcasterId = null;

/**
 * Agrega emotes FFZ desde la respuesta JSON al mapa destino.
 * @param {{ sets?: Record<string, { emoticons?: FfzEmoticon[] }> }} data
 * @param {EmotesMap} emotes
 */
function collectFfzEmotes(data, emotes) {
  if (!data?.sets) return;
  Object.values(data.sets).forEach(set => {
    if (!Array.isArray(set?.emoticons)) return;
    set.emoticons.forEach(emote => {
      const rawUrl = emote.urls?.['2'] || emote.urls?.['1'];
      const safeUrl = sanitizeHttpUrl(rawUrl);
      if (safeUrl && emote.name) {
        emotes[emote.name] = { url: safeUrl, provider: 'ffz' };
      }
    });
  });
}

/**
 * Agrega emotes BTTV al mapa destino.
 * @param {BttvEmote[]} list
 * @param {EmotesMap} emotes
 */
function collectBttvEmotes(list, emotes) {
  list.forEach(emote => {
    if (!emote?.id || !emote?.code) return;
    const safeUrl = sanitizeHttpUrl(
      `https://cdn.betterttv.net/emote/${encodeURIComponent(emote.id)}/2x`
    );
    if (safeUrl) {
      emotes[emote.code] = { url: safeUrl, provider: 'bttv' };
    }
  });
}

/**
 * Obtiene los emotes globales y de canal de BTTV y FFZ de forma paralela.
 * @param {string} broadcasterId - ID numérico del canal en Twitch.
 * @returns {Promise<EmotesMap>} Mapa de emoteCode -> {url, provider}
 */
export async function fetchEmotes(broadcasterId) {
  if (cachedEmotes && cachedBroadcasterId === broadcasterId) {
    return cachedEmotes;
  }

  /** @type {EmotesMap} */
  const emotes = {};

  /** @type {Array<Promise<void>>} */
  const fetchPromises = [
    fetch('https://api.betterttv.net/3/cached/emotes/global')
      .then(async res => {
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            collectBttvEmotes(/** @type {BttvEmote[]} */ (data), emotes);
          }
        }
      })
      .catch(() => {}),

    fetch('https://api.frankerfacez.com/v1/set/global')
      .then(async res => {
        if (res.ok) {
          const data = await res.json();
          collectFfzEmotes(data, emotes);
        }
      })
      .catch(() => {}),
  ];

  if (broadcasterId) {
    const encodedId = encodeURIComponent(String(broadcasterId));
    fetchPromises.push(
      fetch(`https://api.betterttv.net/3/cached/users/twitch/${encodedId}`)
        .then(async res => {
          if (res.ok) {
            const data = await res.json();
            const list = [...(data.channelEmotes || []), ...(data.sharedEmotes || [])];
            collectBttvEmotes(list, emotes);
          }
        })
        .catch(() => {}),

      fetch(`/api/emotes/ffz/${encodedId}`)
        .then(async res => {
          if (res.ok) {
            const data = await res.json();
            collectFfzEmotes(data, emotes);
          }
        })
        .catch(() => {})
    );
  }

  await Promise.allSettled(fetchPromises);

  cachedEmotes = emotes;
  cachedBroadcasterId = broadcasterId;
  return emotes;
}

/**
 * Procesa el texto de un mensaje reemplazando emotes por imágenes.
 * Prioridad: emotes nativos de Twitch > BTTV/FFZ.
 * @param {string | undefined} text - Texto del mensaje de chat.
 * @param {EmotesMap | null | undefined} bttvFfzMap - Mapa de emotes BTTV/FFZ cargados.
 * @param {TwitchEmote[] | null | undefined} twitchEmotes - Lista de emotes nativos [{id, text}].
 * @returns {Array<ReturnType<typeof html> | string> | string | undefined} Array mixto de nodos Preact y texto, o texto plano.
 */
export function parseEmotes(text, bttvFfzMap, twitchEmotes) {
  if (!text) return text;

  const hasTwitch = Boolean(twitchEmotes && twitchEmotes.length > 0);
  const hasBttvFfz = Boolean(bttvFfzMap && Object.keys(bttvFfzMap).length > 0);
  if (!hasBttvFfz && !hasTwitch) return text;

  /** @type {Record<string, string> | null} */
  let twitchMap = null;
  if (hasTwitch && twitchEmotes) {
    twitchMap = {};
    twitchEmotes.forEach(e => {
      const safeUrl = sanitizeHttpUrl(
        `${TWITCH_EMOTE_CDN}/${encodeURIComponent(e.id)}/default/dark/2.0`
      );
      if (safeUrl && twitchMap) {
        twitchMap[e.text] = safeUrl;
      }
    });
  }

  const parts = text.split(/(\s+)/);
  const hasEmote = parts.some(
    p => (twitchMap && Object.hasOwn(twitchMap, p)) || (bttvFfzMap && Object.hasOwn(bttvFfzMap, p))
  );
  if (!hasEmote) return text;

  return parts.map(part => {
    if (twitchMap && Object.hasOwn(twitchMap, part)) {
      return html`<img class="chat-emote" src=${twitchMap[part]} alt=${part} title=${part} />`;
    }
    if (bttvFfzMap && Object.hasOwn(bttvFfzMap, part)) {
      const emote = bttvFfzMap[part];
      const safeUrl = sanitizeHttpUrl(emote?.url);
      if (safeUrl) {
        return html`<img class="chat-emote" src=${safeUrl} alt=${part} title=${part} />`;
      }
    }
    return part;
  });
}
