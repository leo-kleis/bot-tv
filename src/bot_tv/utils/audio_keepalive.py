"""Audio keep-alive para el sistema anfitrión (Windows) mediante winsound."""

from __future__ import annotations

import json
import logging
import math
import struct
import sys
import tempfile
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_FREQUENCY_HZ: float = 60.0
DEFAULT_VOLUME_PCT: float = 3.0
SAMPLE_RATE: int = 44100
DEFAULT_DURATION_SEC: float = 2.0

TEST_BEEP_FREQ_HZ: int = 440
TEST_BEEP_DURATION_MS: int = 250

CONFIG_FILE = Path.home() / ".bot_tv_audio_keepalive.json"
WAV_TEMP_PATH = Path(tempfile.gettempdir()) / "bot_tv_audio_keepalive.wav"


@dataclass
class AudioKeepAliveConfig:
    enabled: bool = False
    volume: float = DEFAULT_VOLUME_PCT
    frequency: float = DEFAULT_FREQUENCY_HZ


class AudioKeepAliveManager:
    """Gestiona la reproducción de un tono tenue continuo en Windows."""

    def __init__(self) -> None:
        self._is_running: bool = False
        self._config: AudioKeepAliveConfig = self._load_config()
        self._supported: bool = sys.platform == "win32"

        if not self._supported:
            LOGGER.warning(
                "Audio keep-alive sólo está soportado en sistemas operativos Windows."
            )

    @property
    def is_supported(self) -> bool:
        return self._supported

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def config(self) -> AudioKeepAliveConfig:
        return self._config

    def _load_config(self) -> AudioKeepAliveConfig:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                    return AudioKeepAliveConfig(
                        enabled=bool(data.get("enabled", False)),
                        volume=float(data.get("volume", DEFAULT_VOLUME_PCT)),
                        frequency=float(data.get("frequency", DEFAULT_FREQUENCY_HZ)),
                    )
            except Exception:
                LOGGER.warning(
                    "No se pudo cargar la configuración de audio keep-alive. "
                    "Usando valores por defecto."
                )
        return AudioKeepAliveConfig()

    def _save_config(self) -> None:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(asdict(self._config), f, indent=2)
        except Exception:
            LOGGER.warning("No se pudo guardar la configuración de audio keep-alive.")

    def _generate_wav(self, freq: float, volume_pct: float) -> Path:
        samples_per_cycle = max(1, round(SAMPLE_RATE / freq))
        adjusted_freq = SAMPLE_RATE / samples_per_cycle
        cycles = max(1, round(DEFAULT_DURATION_SEC * adjusted_freq))
        total_samples = cycles * samples_per_cycle

        clamped_vol = max(0.5, min(30.0, volume_pct))
        max_amp = 32767.0
        amplitude = max_amp * (clamped_vol / 100.0)

        frames = bytearray()
        for i in range(total_samples):
            t = 2.0 * math.pi * adjusted_freq * (i / SAMPLE_RATE)
            val = int(amplitude * math.sin(t))
            frames.extend(struct.pack("<h", val))

        with wave.open(str(WAV_TEMP_PATH), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(frames)

        return WAV_TEMP_PATH

    def start(self) -> bool:
        if not self._supported:
            return False

        import winsound

        try:
            wav_file = self._generate_wav(self._config.frequency, self._config.volume)
            winsound.PlaySound(
                str(wav_file),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
            )
            self._is_running = True
            LOGGER.info(
                "Audio keep-alive iniciado en host (%.1f Hz, vol: %.1f%%)",
                self._config.frequency,
                self._config.volume,
            )
            return True
        except Exception as exc:
            LOGGER.error("Error al iniciar audio keep-alive: %s", exc)
            self._is_running = False
            return False

    def stop(self) -> None:
        if not self._supported:
            return

        import winsound

        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
            self._is_running = False
            LOGGER.info("Audio keep-alive detenido en host.")
        except Exception as exc:
            LOGGER.error("Error al detener audio keep-alive: %s", exc)

    def update_settings(
        self,
        enabled: bool,
        volume: float | None = None,
        frequency: float | None = None,
    ) -> dict[str, object]:
        self._config.enabled = enabled
        if volume is not None:
            self._config.volume = max(0.5, min(30.0, volume))
        if frequency is not None:
            self._config.frequency = max(30.0, min(300.0, frequency))

        self._save_config()

        if self._config.enabled:
            self.start()
        else:
            self.stop()

        return self.get_status()

    def test_beep(self) -> bool:
        if not self._supported:
            return False

        import winsound

        try:
            winsound.Beep(TEST_BEEP_FREQ_HZ, TEST_BEEP_DURATION_MS)
            if self._is_running and self._config.enabled:
                self.start()
            return True
        except Exception as exc:
            LOGGER.error("Error al emitir sonido de prueba en host: %s", exc)
            return False

    def get_status(self) -> dict[str, object]:
        return {
            "supported": self._supported,
            "enabled": self._config.enabled,
            "running": self._is_running,
            "volume": self._config.volume,
            "frequency": self._config.frequency,
        }


AUDIO_KEEP_ALIVE = AudioKeepAliveManager()
