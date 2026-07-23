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

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
PIPER_VOICE = os.getenv("PIPER_VOICE", "")

SYSTEM_PROMPT = ("Eres un asistente de voz local. Responde en espanol, "
                 "en dos o tres frases como maximo: la respuesta se leera "
                 "en voz alta.")


def record(seconds: int = 5) -> Path | None:
    # Graba con sox (rec) o arecord si estan disponibles; si no, None
    out = Path(tempfile.gettempdir()) / "voice_input.wav"
    if shutil.which("rec"):
        cmd = ["rec", "-q", str(out), "trim", "0", str(seconds)]
    elif shutil.which("arecord"):
        cmd = ["arecord", "-q", "-d", str(seconds), "-f", "cd", str(out)]
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


if __name__ == "__main__":
    sys.exit(main())
