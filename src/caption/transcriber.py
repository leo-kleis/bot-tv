from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import numpy as np

from caption.config import (
    CAPTION_INITIAL_PROMPT,
    CAPTION_LANGUAGE,
    CAPTION_MODEL,
    SAMPLE_RATE,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


LOGGER = logging.getLogger(__name__)


class Transcriber:
    """Procesa chunks de audio usando faster-whisper en GPU de manera asíncrona."""

    def __init__(
        self,
        *,
        model_size: str = CAPTION_MODEL,
        language: str = CAPTION_LANGUAGE,
        silence_threshold: float = 0.02,
        max_buffer_sec: float = 5.0,
        silence_duration_sec: float = 0.6,
    ) -> None:
        self.model_size = model_size
        self.language = language
        self.silence_threshold = silence_threshold
        self.max_buffer_samples = int(SAMPLE_RATE * max_buffer_sec)
        self.silence_samples_limit = int(SAMPLE_RATE * silence_duration_sec)

        self._model: Any = None
        self._audio_buffer: list[np.ndarray] = []
        self._consecutive_silence_samples = 0
        self._is_transcribing = False

    def load_model(self) -> None:
        """Carga el modelo de Whisper en la GPU (CUDA)."""
        import sys
        
        # En Windows, las restricciones de seguridad de Python 3.8+
        # impiden buscar DLLs en PATH.
        # Buscamos y agregamos los directorios del CUDA Toolkit
        # y site-packages.
        if sys.platform == "win32":
            import os
            import site
            from pathlib import Path
            
            # 1. Buscar en instalaciones del sistema
            cuda_path = "C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA"
            cuda_base = Path(cuda_path)
            if cuda_base.exists():
                for v_dir in cuda_base.iterdir():
                    bin_dir = v_dir / "bin"
                    if bin_dir.exists():
                        try:
                            os.add_dll_directory(str(bin_dir))
                            os.environ["PATH"] = (
                                str(bin_dir) + os.pathsep + os.environ["PATH"]
                            )
                            LOGGER.info(
                                "Se añadió DLL de CUDA del sistema: %s",
                                bin_dir,
                            )
                        except Exception:
                            pass
            
            # 2. Buscar en librerías nvidia en site-packages (pip)
            for sp_dir in site.getsitepackages():
                nvidia_dir = Path(sp_dir) / "nvidia"
                if nvidia_dir.exists():
                    for lib_dir in nvidia_dir.iterdir():
                        bin_dir = lib_dir / "bin"
                        if bin_dir.exists():
                            try:
                                os.add_dll_directory(str(bin_dir))
                                os.environ["PATH"] = (
                                    str(bin_dir)
                                    + os.pathsep
                                    + os.environ["PATH"]
                                )
                                LOGGER.info(
                                    "Se añadió DLL local de NVIDIA: %s",
                                    bin_dir,
                                )
                            except Exception:
                                pass

        from rich.console import Console

        console = Console()
        status_msg = (
            f"[bold cyan]Cargando modelo '{self.model_size}' en GPU (CUDA)...[/]\n"
            "[dim]Si es la primera vez, se descargarán ~500MB automáticamente. "
            "Por favor, espera...[/]"
        )

        with console.status(status_msg, spinner="dots"):
            try:
                # Importación local diferida
                from faster_whisper import WhisperModel
                
                # Intentamos usar CUDA con selección automática
                # del tipo de cómputo para máxima compatibilidad
                self._model = WhisperModel(
                    self.model_size,
                    device="cuda",
                    compute_type="auto",
                )
                msg = (
                    f"[bold green]Modelo Whisper '{self.model_size}' "
                    "cargado en GPU.[/]"
                )
                console.print(msg)
            except Exception as e:
                LOGGER.error(
                    "Error crítico: No se pudo cargar el modelo en GPU (CUDA). "
                    "La ejecución requiere GPU. Detalle: %s",
                    e,
                )
                raise RuntimeError(
                    "Fallo al inicializar faster-whisper en GPU (CUDA)."
                ) from e

    def _execute_transcribe(self, audio_data: np.ndarray) -> str:
        """Ejecuta la transcripción síncrona en un hilo separado.

        Retorna el texto limpio de la transcripción.
        """
        if self._model is None:
            return ""

        # Usamos vad_filter=True para filtrar silencios eficientemente a nivel de modelo
        segments, info = self._model.transcribe(
            audio_data,
            language=self.language,
            beam_size=5,
            temperature=0.0,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            vad_filter=True,
            vad_parameters=dict(min_speech_duration_ms=250),
            initial_prompt=CAPTION_INITIAL_PROMPT,
        )

        texts = [segment.text.strip() for segment in segments]
        return " ".join(texts).strip()

    async def process_audio_chunk(
        self,
        chunk: np.ndarray,
        on_text_callback: Callable[[str, bool], Coroutine[Any, Any, None]],
    ) -> None:
        """Procesa un nuevo chunk de audio.

        Acumula el buffer y maneja cortes de oración por silencio.
        """
        rms = float(np.sqrt(np.mean(chunk**2))) if len(chunk) > 0 else 0.0

        # Si el buffer está vacío y el volumen es muy bajo, ignoramos el chunk
        if not self._audio_buffer and rms < self.silence_threshold:
            return

        self._audio_buffer.append(chunk)

        if rms < self.silence_threshold:
            self._consecutive_silence_samples += len(chunk)
        else:
            self._consecutive_silence_samples = 0

        if self._is_transcribing:
            return

        total_samples = sum(len(c) for c in self._audio_buffer)

        # Transcribimos si acumulamos al menos 1.0 segundos de audio activo
        if total_samples >= SAMPLE_RATE:
            self._is_transcribing = True
            audio_to_process = np.concatenate(self._audio_buffer)
            
            loop = asyncio.get_running_loop()
            try:
                text = await loop.run_in_executor(
                    None,
                    self._execute_transcribe,
                    audio_to_process,
                )

                is_final = (
                    self._consecutive_silence_samples >= self.silence_samples_limit
                    or total_samples >= self.max_buffer_samples
                )

                if text:
                    await on_text_callback(text, is_final)
                elif total_samples >= SAMPLE_RATE * 3.0:
                    # Limpieza preventiva tras 3 segundos continuos de silencio/ruido
                    is_final = True

                if is_final:
                    self._audio_buffer.clear()
                    self._consecutive_silence_samples = 0

            except Exception:
                LOGGER.exception("Error durante la transcripción de audio")
            finally:
                self._is_transcribing = False
