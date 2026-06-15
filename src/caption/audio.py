from __future__ import annotations

import asyncio
import logging
from types import TracebackType
from typing import TYPE_CHECKING

import numpy as np

from caption.config import CHANNELS, SAMPLE_RATE

if TYPE_CHECKING:
    import numpy.typing as npt
    import sounddevice as sd

LOGGER = logging.getLogger(__name__)


class AudioCapture:
    """Captura de audio desde el micrófono en formato float32 compatible con Whisper."""

    device: int | None
    channels: int
    samplerate: int
    blocksize: int
    _queue: asyncio.Queue[npt.NDArray[np.float32]]
    _loop: asyncio.AbstractEventLoop | None
    _stream: sd.InputStream | None
    _running: bool

    def __init__(
        self,
        *,
        device: int | None = None,
        channels: int = CHANNELS,
        samplerate: int = SAMPLE_RATE,
        chunk_duration_sec: float = 0.5,
    ) -> None:
        self.device = device
        self.channels = channels
        self.samplerate = samplerate
        self.blocksize = int(samplerate * chunk_duration_sec)

        self._queue: asyncio.Queue[npt.NDArray[np.float32]] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream = None
        self._running = False

    def _audio_callback(
        self,
        indata: npt.NDArray[np.float32],
        frames: int,
        time_info: dict[str, float],
        status: sd.CallbackFlags,
    ) -> None:
        """Callback invocado por sounddevice desde un hilo nativo de audio."""
        if status:
            LOGGER.warning("Estado de audio inusual: %s", status)

        if not self._running or self._loop is None:
            return

        # indata tiene shape (frames, channels), lo aplanamos a mono si es de 1 canal
        data_copy = indata.copy().flatten()

        # Enviamos los datos de forma segura al loop de asyncio del hilo principal
        self._loop.call_soon_threadsafe(self._queue.put_nowait, data_copy)

    def start(self) -> None:
        """Inicia la captura de audio."""
        if self._running:
            return

        self._loop = asyncio.get_running_loop()
        self._running = True

        try:
            # Importación local diferida de sounddevice
            import sounddevice as sd

            self._stream = sd.InputStream(
                device=self.device,
                channels=self.channels,
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            LOGGER.info(
                "Captura de audio iniciada en dispositivo: %s",
                self.device or "Predeterminado",
            )
        except Exception:
            self._running = False
            self._loop = None
            LOGGER.exception("Error al iniciar el stream de captura de audio")
            raise

    def stop(self) -> None:
        """Detiene la captura de audio."""
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                LOGGER.exception("Error al detener el stream de captura de audio")
            finally:
                self._stream = None

        self._loop = None
        LOGGER.info("Captura de audio detenida.")

    async def get_chunk(self) -> npt.NDArray[np.float32]:
        """Espera y obtiene el siguiente chunk de audio capturado."""
        return await self._queue.get()

    async def __aenter__(self) -> AudioCapture:
        self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop()
