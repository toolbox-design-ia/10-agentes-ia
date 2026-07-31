"""Voice activity detection (chapter 12): decide when the user stopped talking.

La ventana fija de N segundos es la simplificacion que mas se nota al usar un
asistente: corta las frases largas y hace esperar en las cortas. El VAD la
sustituye por una regla que depende de la senal: empieza a grabar cuando hay
voz y para cuando hay silencio suficiente.

Dos detectores intercambiables:
  * EnergyVAD  — umbral de energia (RMS). Sin dependencias, se calibra con el
    ruido real de la sala. Suficiente en un cuarto silencioso.
  * WebRtcVAD  — el detector de WebRTC (paquete `webrtcvad-wheels`), entrenado
    para distinguir voz de ruido. Aguanta un ventilador o trafico de fondo.

La captura vive aparte a proposito: la maquina de estados que decide el fin de
turno se prueba con audio sintetico, sin microfono ni PortAudio.
"""
from __future__ import annotations

import math
import os
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 16_000        # Whisper trabaja a 16 kHz mono
FRAME_MS = 30               # webrtcvad admite 10, 20 o 30 ms
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000     # 480
FRAME_BYTES = FRAME_SAMPLES * 2                    # PCM 16 bits


def rms(frame: bytes) -> float:
    """Energia media de un frame PCM de 16 bits con signo."""
    if not frame:
        return 0.0
    muestras = struct.unpack(f"<{len(frame) // 2}h", frame[: len(frame) // 2 * 2])
    return math.sqrt(sum(m * m for m in muestras) / len(muestras))


class EnergyVAD:
    """Umbral de energia. Barato, y suficiente si la sala esta en silencio."""

    def __init__(self, threshold: float = 500.0):
        self.threshold = threshold

    def is_speech(self, frame: bytes) -> bool:
        return rms(frame) >= self.threshold

    @classmethod
    def calibrated(cls, silence: bytes, margin: float = 3.0,
                   floor: float = 120.0) -> "EnergyVAD":
        """Fija el umbral a partir de unos segundos de silencio de la sala."""
        frames = [silence[i:i + FRAME_BYTES]
                  for i in range(0, len(silence) - FRAME_BYTES + 1, FRAME_BYTES)]
        ruido = max((rms(f) for f in frames), default=0.0)
        return cls(threshold=max(ruido * margin, floor))


class WebRtcVAD:
    """Detector de WebRTC: distingue voz de ruido, no solo alto de bajo."""

    def __init__(self, aggressiveness: int = 2):
        import webrtcvad  # dependencia opcional; se importa al usarla
        self._vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: bytes) -> bool:
        if len(frame) != FRAME_BYTES:
            return False
        return self._vad.is_speech(frame, SAMPLE_RATE)


def make_detector(kind: str = "", aggressiveness: int = 2):
    """Elige detector; si webrtcvad no esta instalado, cae a energia."""
    kind = (kind or os.getenv("VAD_BACKEND", "webrtc")).lower()
    if kind == "energy":
        return EnergyVAD()
    try:
        return WebRtcVAD(aggressiveness)
    except Exception:
        return EnergyVAD()


@dataclass
class TurnResult:
    audio: bytes
    reason: str          # "silence" | "max_duration" | "no_speech"
    speech_ms: int


class TurnDetector:
    """Maquina de estados: espera voz, la acumula y corta tras el silencio.

    - start_ms:   voz continua necesaria para dar por empezado el turno
                  (evita que un golpe o una tos disparen la grabacion).
    - silence_ms: silencio necesario para darlo por terminado. Es el parametro
                  que se paga en latencia: todo lo que se espere aqui se suma
                  al tiempo de respuesta.
    """

    def __init__(self, detector=None, start_ms: int = 150,
                 silence_ms: int = 700, max_ms: int = 15_000,
                 preroll_ms: int = 300):
        self.detector = detector or make_detector()
        self.start_frames = max(1, start_ms // FRAME_MS)
        self.silence_frames = max(1, silence_ms // FRAME_MS)
        self.max_frames = max_ms // FRAME_MS
        self.preroll_frames = preroll_ms // FRAME_MS
        self.reset()

    def reset(self) -> None:
        self._buffer: list[bytes] = []
        self._preroll: list[bytes] = []
        self._voiced = 0
        self._silence = 0
        self._started = False
        self._frames = 0

    def push(self, frame: bytes) -> TurnResult | None:
        """Devuelve el turno cuando termina; None mientras siga abierto."""
        self._frames += 1
        habla = self.detector.is_speech(frame)

        if not self._started:
            # Guardamos un poco de audio previo: la primera silaba suele caer
            # antes de que el detector confirme que hay voz
            self._preroll.append(frame)
            if len(self._preroll) > self.preroll_frames:
                self._preroll.pop(0)
            self._voiced = self._voiced + 1 if habla else 0
            if self._voiced >= self.start_frames:
                self._started = True
                self._buffer = list(self._preroll)
                self._silence = 0
            elif self._frames >= self.max_frames:
                return TurnResult(b"", "no_speech", 0)
            return None

        self._buffer.append(frame)
        self._silence = 0 if habla else self._silence + 1
        if self._silence >= self.silence_frames:
            util = self._buffer[: len(self._buffer) - self._silence]
            return TurnResult(b"".join(util), "silence", len(util) * FRAME_MS)
        if len(self._buffer) >= self.max_frames:
            return TurnResult(b"".join(self._buffer), "max_duration",
                              len(self._buffer) * FRAME_MS)
        return None

    def feed_pcm(self, pcm: bytes) -> TurnResult | None:
        """Recorre un PCM completo en frames. Util para probar sin microfono."""
        for i in range(0, len(pcm) - FRAME_BYTES + 1, FRAME_BYTES):
            resultado = self.push(pcm[i:i + FRAME_BYTES])
            if resultado is not None:
                return resultado
        return None


# --------------------------------------------------------------------------
# Captura desde el microfono
# --------------------------------------------------------------------------
def record_turn(detector=None, silence_ms: int = 700, max_ms: int = 15_000,
                calibrate_ms: int = 400, on_state=None) -> bytes:
    """Graba hasta que el usuario deja de hablar. Requiere sounddevice."""
    import queue

    import sounddevice as sd  # necesita la libreria PortAudio del sistema

    cola: "queue.Queue[bytes]" = queue.Queue()

    def callback(indata, frames, time_info, status):
        cola.put(bytes(indata))

    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=FRAME_SAMPLES,
                           dtype="int16", channels=1, callback=callback):
        if detector is None:
            # Calibrar con el ruido real de la sala antes de escuchar
            silencio = b""
            for _ in range(max(1, calibrate_ms // FRAME_MS)):
                silencio += cola.get()
            detector = make_detector()
            if isinstance(detector, EnergyVAD):
                detector = EnergyVAD.calibrated(silencio)
        turno = TurnDetector(detector, silence_ms=silence_ms, max_ms=max_ms)
        if on_state:
            on_state("escuchando")
        while True:
            resultado = turno.push(cola.get())
            if resultado is not None:
                if on_state:
                    on_state(f"fin de turno ({resultado.reason})")
                return resultado.audio


def write_wav(path: Path, pcm: bytes, sample_rate: int = SAMPLE_RATE) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return path


def read_wav(path: Path) -> bytes:
    with wave.open(str(path), "rb") as handle:
        assert handle.getframerate() == SAMPLE_RATE, "se espera 16 kHz"
        assert handle.getnchannels() == 1, "se espera mono"
        return handle.readframes(handle.getnframes())
