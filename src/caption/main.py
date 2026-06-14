from __future__ import annotations

import asyncio
import logging
import sys

from bot_tv.utils.logger import setup_logging
from caption.config import CAPTION_DEVICE, CAPTION_HOST, CAPTION_PORT

LOGGER = logging.getLogger(__name__)


async def main_async() -> None:
    """Función asíncrona principal para correr el servicio de subtítulos."""
    from rich.console import Console
    
    console = Console()
    with console.status(
        "[bold green]Cargando módulos de audio y servidor web...",
        spinner="dots",
    ):
        # Imports diferidos para diagnóstico visual rápido
        from caption.audio import AudioCapture
        from caption.server import CaptionServer
        from caption.transcriber import Transcriber

    console.print("[bold green]Dependencias cargadas con exito.[/]")

    console.print("[bold cyan]Inicializando componentes de audio y servidor...[/]")
    server = CaptionServer(host=CAPTION_HOST, port=CAPTION_PORT)
    transcriber = Transcriber()
    audio_capture = AudioCapture(device=CAPTION_DEVICE)

    # Definimos el callback asíncrono para propagar textos transcritos
    async def on_transcription_text(text: str, is_final: bool) -> None:
        LOGGER.info("[%s] %s", "FINAL" if is_final else "PARCIAL", text)
        await server.broadcast(text, is_final)

    try:
        # Cargar el modelo de Whisper (operación síncrona/pesada inicial)
        transcriber.load_model()
        
        # Iniciar el servidor WebSocket
        await server.start()
        console.print(
            f"[bold green]Servidor WebSocket de subtitulos activo en: ws://{CAPTION_HOST}:{CAPTION_PORT}/ws[/]"
        )

        # Iniciamos la captura de audio usando el gestor de contexto asíncrono
        async with audio_capture:
            console.print(
                "[bold green]Subtitulos listos. Habla por el microfono.[/]"
            )
            while True:
                # Esperar por el siguiente fragmento de audio del micrófono
                chunk = await audio_capture.get_chunk()
                # Procesar el chunk en segundo plano de manera no bloqueante
                await transcriber.process_audio_chunk(chunk, on_transcription_text)

    except asyncio.CancelledError:
        LOGGER.warning("Tarea del transcriptor cancelada.")
    except Exception:
        LOGGER.exception("Error fatal en el servicio de subtítulos")
        raise
    finally:
        # Apagado ordenado
        await server.stop()
        LOGGER.info("Servicio de subtítulos finalizado.")


def main() -> None:
    """Punto de entrada principal del script bot-caption."""
    setup_logging(level=logging.INFO)
    LOGGER.info("Iniciando servicio independiente de subtítulos (bot-caption)...")

    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        LOGGER.warning("Apagando servicio de subtítulos por solicitud del usuario...")
        sys.exit(0)


if __name__ == "__main__":
    main()
