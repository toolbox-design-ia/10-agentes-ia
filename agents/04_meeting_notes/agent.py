"""Meeting notes (chapter 7): from audio to structured minutes, offline.

Transcribe la grabacion con Whisper (local) y redacta el acta con el modelo
local: resumen, decisiones y tareas con responsable. El audio nunca sale de
tu maquina.
"""
import os
import sys
from pathlib import Path

import ollama
from dotenv import load_dotenv

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def transcribe(audio_path: Path) -> str:
    import whisper  # import aqui: el paquete es pesado y solo lo usa este agente

    model = whisper.load_model(WHISPER_MODEL)
    result = model.transcribe(str(audio_path), language="es")
    return result["text"].strip()


def write_minutes(transcript: str) -> str:
    prompt = (PROMPTS_DIR / "meeting_minutes.txt").read_text(encoding="utf-8")
    return ollama.generate(
        model=MODEL,
        prompt=prompt.format(transcript=transcript[:12000]),
    )["response"].strip()


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("Uso: python agent.py <grabacion.mp3|wav|m4a>")
        print("La transcripcion y el acta se guardan junto al audio.")
        return 1
    audio_path = Path(args[0])
    if not audio_path.is_file():
        print(f"No existe el archivo {audio_path}")
        return 1
    print(f"Transcribiendo con Whisper ({WHISPER_MODEL})... "
          "la primera vez descarga el modelo.")
    transcript = transcribe(audio_path)
    transcript_file = audio_path.with_suffix(".transcripcion.txt")
    transcript_file.write_text(transcript, encoding="utf-8")
    print(f"Transcripcion guardada: {transcript_file.name}")
    print("Redactando el acta...")
    minutes = write_minutes(transcript)
    minutes_file = audio_path.with_suffix(".acta.md")
    minutes_file.write_text(minutes, encoding="utf-8")
    print(f"Acta guardada: {minutes_file.name}\n\n{minutes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
