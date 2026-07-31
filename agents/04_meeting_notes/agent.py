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

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.base_agent import BaseAgent  # noqa: E402

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
    """Dos pasadas con validacion de esquema; una sola llamada si falla.

    La ruta buena es minutes.build_minutes(): primera pasada permisiva para
    sacar candidatos, segunda estricta que valida contra un modelo Pydantic y
    reintenta si el modelo no cumple el formato. Si aun asi no converge, se
    entrega el acta en una sola pasada antes que no entregar nada, avisando.
    """
    import importlib
    minutes = importlib.import_module("agents.04_meeting_notes.minutes")
    try:
        return minutes.build_minutes(transcript).to_markdown()
    except ValueError as exc:
        print(f"  (Aviso: la validacion de esquema no convergio: {exc})")
        print("  Entrego el acta en una sola pasada, sin validar.")
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

# ---------------------------------------------------------------------------
# El patron del capitulo 3: este agente expuesto como herramientas
# ---------------------------------------------------------------------------

def tool_transcribe(audio_path: str) -> str:
    ruta = Path(audio_path)
    if not ruta.is_file():
        return f"No existe el archivo {ruta}."
    texto = transcribe(ruta)
    return texto[:4000]


def tool_write_minutes(transcript: str) -> str:
    return write_minutes(transcript)


class MeetingNotesAgent(BaseAgent):
    """Capitulo 7 sobre el patron del capitulo 3."""

    system_prompt = (
        "Conviertes grabaciones de reuniones en actas. Primero transcribe el "
        "audio con transcribe, despues redacta el acta con write_minutes. "
        "No inventes decisiones ni responsables que no esten en la transcripcion."
    )
    tools = {
        "transcribe": {
            "description": "Transcribe un archivo de audio con Whisper local",
            "params": {"audio_path": "ruta del archivo de audio"},
            "func": tool_transcribe,
        },
        "write_minutes": {
            "description": "Redacta el acta a partir de una transcripcion",
            "params": {"transcript": "texto de la transcripcion"},
            "func": tool_write_minutes,
        },
    }


if __name__ == "__main__":
    sys.exit(main())
