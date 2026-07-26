import { html } from 'preact-setup';

const TWITCH_EMOTE_CDN = 'https://static-cdn.jtvnw.net/emoticons/v2';

let cachedEmotes = null;
let cachedBroadcasterId = null;

/**
 * Obtiene los emotes globales y de canal de BTTV y FFZ de forma paralela.
 * @param {string} broadcasterId - ID numerico del canal en Twitch.
 * @returns {Promise<Object>} Mapa de emoteCode -> {url, provider}
 */
export async function fetchEmotes(broadcasterId) {
  if (cachedEmotes && cachedBroadcasterId === broadcasterId) {
    return cachedEmotes;
  }

  const emotes = {};

  const fetchPromises = [
    // 1. BTTV Global
    fetch('https://api.betterttv.net/3/cached/emotes/global')
      .then(async res => {
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            data.forEach(e => {
              emotes[e.code] = {
                url: `https://cdn.betterttv.net/emote/${e.id}/2x`,
                provider: 'bttv',
              };
            });
          }
        }
      })
      .catch(() => {}),

    // 2. FFZ Global
    fetch('https://api.frankerfacez.com/v1/set/global')
      .then(async res => {
        if (res.ok) {
          const data = await res.json();
          if (data.sets) {
            Object.values(data.sets).forEach(set => {
              if (set.emoticons) {
                set.emoticons.forEach(e => {
                  const url = e.urls['2'] || e.urls['1'];
                  emotes[e.name] = { url, provider: 'ffz' };
                });
              }
            });
          }
        }
      })
      .catch(() => {}),
  ];

  if (broadcasterId) {
    fetchPromises.push(
      // 3. BTTV Channel
      fetch(`https://api.betterttv.net/3/cached/users/twitch/${broadcasterId}`)
        .then(async res => {
          if (res.ok) {
            const data = await res.json();
            const list = [...(data.channelEmotes || []), ...(data.sharedEmotes || [])];
            list.forEach(e => {
              emotes[e.code] = {
                url: `https://cdn.betterttv.net/emote/${e.id}/2x`,
                provider: 'bttv',
              };
            });
          }
        })
        .catch(() => {}),

      // 4. FFZ Channel (vía proxy para evitar 404 en consola si el canal no usa FFZ)
      fetch(`/api/emotes/ffz/${broadcasterId}`)
        .then(async res => {
          if (res.ok) {
            const data = await res.json();
            if (data.sets) {
              Object.values(data.sets).forEach(set => {
                if (set.emoticons) {
                  set.emoticons.forEach(e => {
                    const url = e.urls['2'] || e.urls['1'];
                    emotes[e.name] = { url, provider: 'ffz' };
                  });
                }
              });
            }
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
 * Procesa el texto de un mensaje reemplazando emotes por imagenes.
 * Prioridad: emotes nativos de Twitch > BTTV/FFZ.
 * @param {string} text - Texto del mensaje de chat.
 * @param {Object} bttvFfzMap - Mapa de emotes BTTV/FFZ cargados.
 * @param {Array} twitchEmotes - Lista de emotes nativos [{id, text}].
 * @returns {Array|string} Array mixto de nodos Preact y texto, o texto plano.
 */
export function parseEmotes(text, bttvFfzMap, twitchEmotes) {
  if (!text) return text;

  // Construir mapa de emotes nativos de Twitch desde los fragments
  const twitchMap = {};
  if (twitchEmotes && twitchEmotes.length > 0) {
    twitchEmotes.forEach(e => {
      twitchMap[e.text] = `${TWITCH_EMOTE_CDN}/${e.id}/default/dark/2.0`;
    });
  }

  const hasBttvFfz = bttvFfzMap && Object.keys(bttvFfzMap).length > 0;
  const hasTwitch = Object.keys(twitchMap).length > 0;
  if (!hasBttvFfz && !hasTwitch) return text;

  const parts = text.split(/(\s+)/);
  const hasEmote = parts.some(p => twitchMap[p] || (bttvFfzMap && bttvFfzMap[p]));
  if (!hasEmote) return text;

  return parts.map(part => {
    if (twitchMap[part]) {
      return html`<img class="chat-emote" src=${twitchMap[part]} alt=${part} title=${part} />`;
    }
    if (bttvFfzMap && bttvFfzMap[part]) {
      const emote = bttvFfzMap[part];
      return html`<img class="chat-emote" src=${emote.url} alt=${part} title=${part} />`;
    }
    return part;
  });
}
