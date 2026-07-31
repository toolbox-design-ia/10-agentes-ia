"""Voice assistant (chapter 12): Whisper for the ears, Piper for the voice.

Recibe una grabacion (o graba unos segundos si hay microfono y sox/arecord),
la transcribe con Whisper local, responde con el modelo local y, si Piper
esta instalado (PIPER_VOICE en el .env), lee la respuesta en voz alta.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import ollama
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.base_agent import BaseAgent  # noqa: E402

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
PIPER_VOICE = os.getenv("PIPER_VOICE", "")

SYSTEM_PROMPT = ("Eres un asistente de voz local. Responde en espanol, "
                 "en dos o tres frases como maximo: la respuesta se leera "
                 "en voz alta.")


def record(seconds: int = 5) -> Path | None:
    """Graba un turno de habla. Con VAD si se puede; si no, ventana fija.

    El VAD (agents/09_voice_assistant/vad.py) decide el fin de turno por la
    senal: para cuando el usuario deja de hablar, en vez de cortar a los N
    segundos. Necesita sounddevice, que a su vez necesita la libreria
    PortAudio del sistema; si falta, se cae al metodo de la ventana fija con
    sox o arecord, que no depende de nada instalado por pip.
    """
    out = Path(tempfile.gettempdir()) / "voice_input.wav"
    try:
        import importlib
        vad = importlib.import_module("agents.09_voice_assistant.vad")
        print("Escuchando... habla cuando quieras (paro sola al terminar).")
        pcm = vad.record_turn(silence_ms=int(os.getenv("VAD_SILENCE_MS", "700")),
                              on_state=lambda s: print(f"  [{s}]"))
        if not pcm:
            print("No he oido nada.")
            return None
        return vad.write_wav(out, pcm)
    except (ImportError, OSError) as exc:
        print(f"(Sin captura por VAD: {exc}. Uso ventana fija de {seconds} s.)")

    if shutil.which("rec"):
        cmd = ["rec", "-q", "-r", "16000", "-c", "1", str(out),
               "trim", "0", str(seconds)]
    elif shutil.which("arecord"):
        cmd = ["arecord", "-q", "-d", str(seconds), "-r", "16000",
               "-f", "S16_LE", "-c", "1", str(out)]
    else:
        return None
    print(f"Grabando {seconds} segundos... habla ahora.")
    subprocess.run(cmd, check=True)
    return out


def transcribe(audio_path: Path) -> str:
    import whisper  # import aqui: paquete pesado, solo lo usa este agente

    model = whisper.load_model(WHISPER_MODEL)
    return model.transcribe(str(audio_path), language="es")["text"].strip()


def answer(question: str) -> str:
    reply = ollama.chat(model=MODEL, messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ])
    return reply["message"]["content"].strip()


def speak(text: str) -> bool:
    # Piper lee de stdin y escribe un wav; luego se reproduce
    if not (PIPER_VOICE and shutil.which("piper")):
        return False
    wav = Path(tempfile.gettempdir()) / "voice_output.wav"
    subprocess.run(["piper", "--model", PIPER_VOICE, "--output_file", str(wav)],
                   input=text.encode("utf-8"), check=True)
    for player in ("aplay", "afplay", "paplay"):
        if shutil.which(player):
            subprocess.run([player, str(wav)], check=False)
            return True
    return False


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    audio_path = Path(args[0]) if args else record()
    if audio_path is None:
        print("Sin microfono accesible (instala sox o arecord) y sin archivo.")
        print("Uso: python agent.py [grabacion.wav]")
        return 1
    if not audio_path.is_file():
        print(f"No existe el archivo {audio_path}")
        return 1
    print(f"Transcribiendo con Whisper ({WHISPER_MODEL})...")
    question = transcribe(audio_path)
    print(f"Tu: {question}")
    reply = answer(question)
    print(f"Asistente: {reply}")
    if not speak(reply):
        print("(Piper no configurado: respuesta solo en texto. "
              "Ver PIPER_VOICE en el .env y el capitulo 12.)")
    return 0

# ---------------------------------------------------------------------------
# El patron del capitulo 3: este agente expuesto como herramientas
# ---------------------------------------------------------------------------

def tool_transcribe_audio(audio_path: str) -> str:
    ruta = Path(audio_path)
    if not ruta.is_file():
        return f"No existe el archivo {ruta}."
    return transcribe(ruta)


def tool_speak(text: str) -> str:
    return "Reproducido en voz alta." if speak(text) else \
        "Piper no esta configurado (PIPER_VOICE en el .env): solo texto."


class VoiceAssistantAgent(BaseAgent):
    """Capitulo 12 sobre el patron del capitulo 3."""

    system_prompt = (
        "Eres un asistente de voz local. Responde en espanol, en dos o tres "
        "frases como maximo, porque la respuesta se leera en voz alta. Usa "
        "speak para leerla cuando el usuario lo pida."
    )
    tools = {
        "transcribe_audio": {
            "description": "Transcribe un archivo de audio con Whisper local",
            "params": {"audio_path": "ruta del archivo de audio"},
            "func": tool_transcribe_audio,
        },
        "speak": {
            "description": "Lee un texto en voz alta con Piper",
            "params": {"text": "texto a leer"},
            "func": tool_speak,
        },
    }


if __name__ == "__main__":
    sys.exit(main())
