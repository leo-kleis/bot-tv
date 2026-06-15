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
        partial_interval_sec: float = 1.2,
    ) -> None:
        self.model_size = model_size
        self.language = language
        self.silence_threshold = silence_threshold
        self.max_buffer_samples = int(SAMPLE_RATE * max_buffer_sec)
        self.silence_samples_limit = int(SAMPLE_RATE * silence_duration_sec)
        self.partial_interval_samples = int(SAMPLE_RATE * partial_interval_sec)

        self._model: Any = None
        self._audio_buffer: list[np.ndarray] = []
        self._consecutive_silence_samples = 0
        self._is_transcribing = False
        self._samples_since_last_transcription = 0
        self._last_text = ""

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
                                    str(bin_dir) + os.pathsep + os.environ["PATH"]
                                )
                                LOGGER.info(
                                    "Se añadió DLL local de NVIDIA: %s",
                                    bin_dir,
                                )
                            except Exception:
                                pass

        from rich.console import Console

        console = Console()
        try:
            # Importación local diferida
            from faster_whisper import WhisperModel
            from huggingface_hub import snapshot_download
            from huggingface_hub.utils import (
                disable_progress_bars,
                enable_progress_bars,
            )

            repo_id = f"Systran/faster-whisper-{self.model_size}"

            # Intentamos verificar si el modelo ya está localmente
            # en caché de forma silenciosa.
            try:
                disable_progress_bars()
                model_path = snapshot_download(repo_id=repo_id, local_files_only=True)
            except Exception:
                # Si no está en caché, habilitamos barras de progreso
                # para ver la descarga real.
                enable_progress_bars()
                console.print(
                    f"[bold cyan]Descargando modelo '{self.model_size}' "
                    "desde Hugging Face...[/]"
                )
                model_path = snapshot_download(repo_id=repo_id, local_files_only=False)

            status_msg = (
                f"[bold cyan]Cargando modelo '{self.model_size}' en GPU (CUDA)...[/]"
            )

            with console.status(status_msg, spinner="dots"):
                # Inicializamos Whisper con la ruta del modelo local
                self._model = WhisperModel(
                    model_path,
                    device="cuda",
                    compute_type="auto",
                )

            msg = f"[bold green]Modelo Whisper '{self.model_size}' cargado en GPU.[/]"
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

    def _is_prompt_hallucination(self, text: str) -> bool:
        """Determina si el texto transcrito es una alucinación del prompt inicial."""
        cleaned = (
            text.lower()
            .replace(",", "")
            .replace(".", "")
            .replace("¡", "")
            .replace("!", "")
            .replace("?", "")
            .replace("¿", "")
            .strip()
        )
        words = cleaned.split()
        if not words:
            return False

        # Palabras presentes en el prompt inicial
        prompt_words = {
            "hablamos",
            "en",
            "espanol",
            "español",
            "de",
            "chile",
            "usando",
            "modismos",
            "chilenos",
            "weon",
            "weón",
            "wea",
            "po",
            "cachai",
            "altiro",
            "bacan",
            "bacán",
            "fome",
            "pololo",
            "polola",
            "carrete",
            "yapo",
            "sipo",
            "nopo",
            "pega",
            "luca",
            "cuatico",
            "cuático",
            "chanta",
            "pucha",
            "guata",
            "tuto",
            "poto",
            "caña",
            "cana",
            "flaite",
            "pana",
            "lote",
            "engrupido",
        }

        matches = sum(1 for w in words if w in prompt_words)

        # Si tiene 3 o más palabras y el 70% o más pertenecen
        # al prompt, se considera alucinación.
        return len(words) >= 3 and (matches / len(words)) >= 0.7

    def _clean_repetitions(self, text: str) -> str:
        """Limpia bucles de repetición infinita y risas excesivas en el texto."""
        import re

        if not text:
            return ""

        # 1. Colapsar risas infinitas del estilo "jajajajaja", "jejejeje"
        # Reemplazamos secuencias continuas de sílabas repetidas
        # por una risa estándar de 3 sílabas.
        text = re.sub(r"(?i)(ja|je|ji|jo|ju)\1{3,}", r"\1\1\1", text)

        # 2. Colapsar repeticiones de palabras consecutivas idénticas
        # (ej. "ja ja ja ja" o "y y y")
        words = text.split()
        cleaned_words = []
        for word in words:
            # Normalizar para comparar (sin puntuación y en minúsculas)
            norm_word = word.lower().strip(".,;:!?¿¡")

            # Para risas permitimos hasta 3 repeticiones, para otras palabras máximo 2
            max_rep = 3 if norm_word in {"ja", "je", "ji", "jo", "ju"} else 2

            consecutive_count = 0
            for w in reversed(cleaned_words):
                if w.lower().strip(".,;:!?¿¡") == norm_word:
                    consecutive_count += 1
                else:
                    break

            if consecutive_count < max_rep:
                cleaned_words.append(word)

        return " ".join(cleaned_words).strip()

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
            no_speech_threshold=0.65,
            log_prob_threshold=-0.85,
            vad_filter=True,
            vad_parameters=dict(
                min_speech_duration_ms=200,
                max_speech_duration_s=5,
                min_silence_duration_ms=400,
                speech_pad_ms=500,
            ),
            initial_prompt=CAPTION_INITIAL_PROMPT,
        )

        texts = [segment.text.strip() for segment in segments]
        candidate_text = " ".join(texts).strip()

        # Limpiar repeticiones excesivas y alucinaciones de risas
        candidate_text = self._clean_repetitions(candidate_text)

        # Filtrar alucinaciones del prompt inicial
        if self._is_prompt_hallucination(candidate_text):
            LOGGER.warning(
                "Alucinación del prompt inicial detectada y filtrada: %s",
                candidate_text,
            )
            return ""

        return candidate_text

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
        self._samples_since_last_transcription += len(chunk)

        if rms < self.silence_threshold:
            self._consecutive_silence_samples += len(chunk)
        else:
            self._consecutive_silence_samples = 0

        if self._is_transcribing:
            return

        total_samples = sum(len(c) for c in self._audio_buffer)

        # Detectar de antemano si es silencio final o buffer lleno
        is_final = (
            self._consecutive_silence_samples >= self.silence_samples_limit
            or total_samples >= self.max_buffer_samples
        )

        # Transcribir si es final, o si acumulamos suficiente audio nuevo para parciales
        should_transcribe = is_final or (
            total_samples >= SAMPLE_RATE
            and self._samples_since_last_transcription >= self.partial_interval_samples
        )

        if should_transcribe:
            self._is_transcribing = True
            self._samples_since_last_transcription = 0
            audio_to_process = np.concatenate(self._audio_buffer)

            loop = asyncio.get_running_loop()
            try:
                text = await loop.run_in_executor(
                    None,
                    self._execute_transcribe,
                    audio_to_process,
                )

                if text:
                    # Emitir solo si es final o si el texto cambió
                    # respecto al parcial anterior.
                    if is_final or text != self._last_text:
                        await on_text_callback(text, is_final)
                        self._last_text = "" if is_final else text
                elif total_samples >= SAMPLE_RATE * 3.0:
                    # Limpieza preventiva tras 3 segundos continuos de silencio/ruido
                    is_final = True

                if is_final:
                    self._audio_buffer.clear()
                    self._consecutive_silence_samples = 0
                    self._samples_since_last_transcription = 0
                    self._last_text = ""

            except Exception:
                LOGGER.exception("Error durante la transcripción de audio")
            finally:
                self._is_transcribing = False
