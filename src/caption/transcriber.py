from __future__ import annotations

import asyncio
import logging
import os
import re
import site
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from caption.config import (
    CAPTION_INITIAL_PROMPT,
    CAPTION_LANGUAGE,
    CAPTION_MODEL,
    SAMPLE_RATE,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import numpy.typing as npt
    from faster_whisper import WhisperModel


LOGGER = logging.getLogger(__name__)

MIN_WORDS_HALLUCINATION = 3
HALLUCINATION_RATIO_LIMIT = 0.7


class Transcriber:
    """Procesa chunks de audio usando faster-whisper en GPU de manera asíncrona."""

    model_size: str
    language: str
    silence_threshold: float
    max_buffer_samples: int
    silence_samples_limit: int
    partial_interval_samples: int
    _model: WhisperModel | None
    _audio_buffer: list[npt.NDArray[np.float32]]
    _consecutive_silence_samples: int
    _is_transcribing: bool
    _samples_since_last_transcription: int
    _last_text: str

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

        self._model = None
        self._audio_buffer = []
        self._consecutive_silence_samples = 0
        self._is_transcribing = False
        self._samples_since_last_transcription = 0
        self._last_text = ""

    def load_model(self) -> None:
        """Carga el modelo de Whisper en la GPU (CUDA)."""
        # En Windows, las restricciones de seguridad de Python 3.8+
        # impiden buscar DLLs en PATH.
        # Buscamos y agregamos los directorios del CUDA Toolkit
        # y site-packages.
        if sys.platform == "win32":
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

            # Intentamos cargar con float16 para optimizar rendimiento y VRAM.
            # Si la GPU no soporta float16 de forma eficiente (ej. Pascal/GTX 10xx),
            # hacemos fallback dinámico a otros formatos compatibles.
            compute_types = ["float16", "int8_float16", "float32", "auto"]
            loaded = False
            last_err: Exception | None = None

            for comp_type in compute_types:
                try:
                    status_msg = (
                        f"[bold cyan]Cargando modelo '{self.model_size}' "
                        f"en GPU (CUDA, {comp_type})...[/]"
                    )
                    with console.status(status_msg, spinner="dots"):
                        self._model = WhisperModel(
                            model_path,
                            device="cuda",
                            compute_type=comp_type,
                        )
                    msg = (
                        f"[bold green]Modelo Whisper '{self.model_size}' "
                        f"cargado con éxito ({comp_type}).[/]"
                    )
                    console.print(msg)
                    loaded = True
                    break
                except ValueError as ve:
                    LOGGER.warning(
                        "Tipo de computación '%s' no soportado: %s. Reintentando...",
                        comp_type,
                        ve,
                    )
                    last_err = ve

            if not loaded:
                raise RuntimeError(
                    "No se pudo cargar el modelo con ningún compute_type compatible."
                ) from last_err
        except Exception as e:
            LOGGER.exception(
                "Error crítico: No se pudo cargar el modelo en GPU (CUDA). "
                "La ejecución requiere GPU."
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
        return (
            len(words) >= MIN_WORDS_HALLUCINATION
            and (matches / len(words)) >= HALLUCINATION_RATIO_LIMIT
        )

    def _clean_repetitions(self, text: str) -> str:
        """Limpia bucles de repetición infinita y risas excesivas en el texto."""
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

    def _execute_transcribe(self, audio_data: npt.NDArray[np.float32]) -> str:
        """Ejecuta la transcripción síncrona en un hilo separado.

        Retorna el texto limpio de la transcripción.
        """
        if self._model is None:
            return ""

        # Filtrar silencios eficientemente a nivel de modelo con VAD.
        # Ajustar VAD para ignorar ruidos breves y silencios marginales.
        segments, _ = self._model.transcribe(
            audio_data,
            language=self.language,
            beam_size=3,
            temperature=0.0,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            log_prob_threshold=-0.85,
            vad_filter=True,
            vad_parameters={
                "min_speech_duration_ms": 250,
                "max_speech_duration_s": 5,
                "min_silence_duration_ms": 400,
                "speech_pad_ms": 400,
            },
            initial_prompt=CAPTION_INITIAL_PROMPT,
        )

        texts = [segment.text.strip() for segment in segments]
        candidate_text = " ".join(texts).strip()

        # Limpiar repeticiones excesivas y alucinaciones de risas
        candidate_text = self._clean_repetitions(candidate_text)

        # Normalizar modismos y chilenismos comunes mal transcritos
        candidate_text = self._post_process_chilean_spanish(candidate_text)

        # Filtrar alucinaciones de ruido típicas de Whisper (ej: Amara.org)
        if self._is_noise_hallucination(candidate_text):
            LOGGER.warning(
                "Alucinación típica de Whisper detectada y filtrada: %s",
                candidate_text,
            )
            return ""

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
        chunk: npt.NDArray[np.float32],
        on_text_callback: Callable[[str, bool], Awaitable[None]],
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

        # Evitar lag si el procesamiento se retrasa y el buffer crece en exceso
        while sum(len(c) for c in self._audio_buffer) > self.max_buffer_samples:
            if self._audio_buffer:
                removed = self._audio_buffer.pop(0)
                self._samples_since_last_transcription = max(
                    0, self._samples_since_last_transcription - len(removed)
                )

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

    def _post_process_chilean_spanish(self, text: str) -> str:
        """Post-procesa el texto para normalizar chilenismos y modismos comunes."""
        if not text:
            return ""

        # Mapeos de transcripciones comunes o formales a modismos chilenos
        replacements = {
            r"\bhuevón\b": "weón",
            r"\bhuevones\b": "weones",
            r"\bhuevona\b": "weona",
            r"\bhuevonas\b": "weonas",
            r"\bgüeón\b": "weón",
            r"\bgüeona\b": "weona",
            r"\bhuevada\b": "wea",
            r"\bhuevadas\b": "weas",
            r"\bwevada\b": "wea",
            r"\bwevadas\b": "weas",
            r"\bsí po\b": "sipo",
            r"\bsi po\b": "sipo",
            r"\bno po\b": "nopo",
            r"\bya po\b": "yapo",
            r"\bal tiro\b": "altiro",
            r"\bal toque\b": "altoke",
        }

        processed = text
        for pattern, repl in replacements.items():
            processed = re.sub(pattern, repl, processed, flags=re.IGNORECASE)

        return processed

    def _is_noise_hallucination(self, text: str) -> bool:
        """Determina si el texto transcrito es una alucinación típica de Whisper."""
        cleaned = text.lower()
        hallucination_patterns = [
            r"amara\.org",
            r"subtítulos por",
            r"subtítulos de",
            r"subtitulado por",
            r"gracias por ver",
            r"descargado de",
            r"apoya a",
            r"comunidad de amara",
            r"traducción al español",
        ]
        return any(re.search(pattern, cleaned) for pattern in hallucination_patterns)

