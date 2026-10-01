"""Script autónomo para evitar la suspensión de audífonos en Windows.

No requiere servidores, bases de datos ni dependencias externas.
Usa únicamente la biblioteca estándar de Python (winsound).
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

DEFAULT_FREQ_HZ: float = 60.0
DEFAULT_VOLUME_PCT: float = 3.0
SAMPLE_RATE: int = 44100
DURATION_SEC: float = 2.0


def generate_wav(
    dest_path: Path,
    freq: float = DEFAULT_FREQ_HZ,
    volume_pct: float = DEFAULT_VOLUME_PCT,
) -> Path:
    """Genera un archivo WAV de tono continuo calibrado con ciclos cerrados."""
    samples_per_cycle = max(1, round(SAMPLE_RATE / freq))
    adjusted_freq = SAMPLE_RATE / samples_per_cycle
    cycles = max(1, round(DURATION_SEC * adjusted_freq))
    total_samples = cycles * samples_per_cycle

    clamped_vol = max(0.5, min(50.0, volume_pct))
    max_amp = 32767.0
    amplitude = max_amp * (clamped_vol / 100.0)

    frames = bytearray()
    for i in range(total_samples):
        t = 2.0 * math.pi * adjusted_freq * (i / SAMPLE_RATE)
        val = int(amplitude * math.sin(t))
        frames.extend(struct.pack("<h", val))

    with wave.open(str(dest_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(frames)

    return dest_path


def main() -> None:
    """Punto de entrada del script autónomo."""
    if sys.platform != "win32":
        print(
            "Error: Este script requiere Windows para utilizar el subsistema winsound."
        )
        sys.exit(1)

    import winsound

    parser = argparse.ArgumentParser(
        description=(
            "Mantiene activos audífonos Bluetooth o DACs "
            "con una señal continua de 0% CPU."
        )
    )
    parser.add_argument(
        "-v",
        "--volume",
        type=float,
        default=DEFAULT_VOLUME_PCT,
        help=f"Volumen en porcentaje (por defecto: {DEFAULT_VOLUME_PCT}%%)",
    )
    parser.add_argument(
        "-f",
        "--frequency",
        type=float,
        default=DEFAULT_FREQ_HZ,
        help=f"Frecuencia del tono en Hz (por defecto: {DEFAULT_FREQ_HZ} Hz)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Emite un pitido de prueba rápido de 440 Hz y sale",
    )
    args = parser.parse_args()

    if args.test:
        print("Emitiendo pitido de prueba de 440 Hz...")
        winsound.Beep(440, 300)
        print("Prueba finalizada.")
        return

    wav_path = Path(tempfile.gettempdir()) / "standalone_audio_keepalive.wav"
    generate_wav(wav_path, freq=args.frequency, volume_pct=args.volume)

    print("==================================================")
    print("      Anti-suspensión de Audífonos (Standalone)   ")
    print("==================================================")
    print(f" Frecuencia: {args.frequency:.1f} Hz")
    print(f" Volumen: {args.volume:.1f}%")
    print("--------------------------------------------------")
    print(" Presiona Ctrl+C para detener y salir.")
    print("==================================================")

    winsound.PlaySound(
        str(wav_path),
        winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
    )

    import time

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        winsound.PlaySound(None, winsound.SND_PURGE)
        print("\nAudio detenido. Saliendo...")


if __name__ == "__main__":
    main()
