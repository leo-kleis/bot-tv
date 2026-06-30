import { html, useEffect, useRef } from 'preact-setup';

export function StreamTab({ channel }) {
  const containerRef = useRef(null);
  const playerRef = useRef(null);

  useEffect(() => {
    if (!window.Twitch) {
      console.warn('Twitch Embed SDK no está cargado.');
      return;
    }

    if (containerRef.current && !playerRef.current && channel) {
      playerRef.current = new window.Twitch.Player(containerRef.current, {
        channel: channel,
        width: '100%',
        height: '100%',
        parent: [window.location.hostname],
        autoplay: true,
        muted: false,
      });
    }

    // Al desmontarse, limpiamos la referencia.
    // El navegador destruirá automáticamente el iframe eliminando audio y consumo.
    return () => {
      playerRef.current = null;
    };
  }, [channel]);

  return html`
    <div class="stream-tab">
      <div class="stream-player-wrapper">
        <div ref=${containerRef} class="twitch-embed-container"></div>
      </div>
    </div>
  `;
}
