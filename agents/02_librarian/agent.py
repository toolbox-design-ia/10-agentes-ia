"""Librarian (chapter 5): file organizer that proposes before touching.

Regla de oro del capitulo: primero dry-run (solo propone), y solo mueve
con --apply. Clasifica por extension; para documentos de texto ambiguos
pide al modelo una carpeta tematica.
"""
import os
import shutil
import sys
from pathlib import Path

import ollama
from dotenv import load_dotenv

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
FILES_ROOT = Path(os.getenv("FILES_ROOT", str(Path.home() / "Documentos")))

CATEGORIES = {
    "Imagenes": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tiff"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
    "Video": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    "Comprimidos": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Hojas de calculo": {".xlsx", ".xls", ".csv", ".ods"},
    "Presentaciones": {".pptx", ".key", ".odp"},
}
TEXT_LIKE = {".pdf", ".txt", ".md", ".docx"}

TOPIC_PROMPT = """Nombre de archivo: {name}
Primeras lineas (si es texto): {preview}

Elige UNA carpeta tematica de esta lista para guardarlo:
Facturas, Contratos, Manuales, Notas, Proyectos, Personal, Otros
Responde SOLO con el nombre de la carpeta."""


def preview_text(path: Path) -> str:
    if path.suffix.lower() in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")[:400]
    return "(binario)"


def classify(path: Path) -> str:
    suffix = path.suffix.lower()
    for category, extensions in CATEGORIES.items():
        if suffix in extensions:
            return category
    if suffix in TEXT_LIKE:
        prompt = TOPIC_PROMPT.format(name=path.name, preview=preview_text(path))
        topic = ollama.generate(model=MODEL, prompt=prompt)["response"].strip()
        allowed = {"Facturas", "Contratos", "Manuales", "Notas",
                   "Proyectos", "Personal", "Otros"}
        return f"Documentos/{topic if topic in allowed else 'Otros'}"
    return "Otros"


def plan_moves(root: Path) -> list[tuple[Path, Path]]:
    moves = []
    for path in sorted(root.iterdir()):
        if path.is_dir() or path.name.startswith("."):
            continue
        destination = root / classify(path) / path.name
        if destination != path:
            moves.append((path, destination))
    return moves


def main() -> int:
    apply_changes = "--apply" in sys.argv
    if not FILES_ROOT.is_dir():
        print(f"No existe la carpeta {FILES_ROOT} (variable FILES_ROOT del .env).")
        return 1
    moves = plan_moves(FILES_ROOT)
    if not moves:
        print("Nada que organizar: la carpeta ya esta ordenada.")
        return 0
    print(f"{'APLICANDO' if apply_changes else 'PROPUESTA (dry-run)'} "
          f"— {len(moves)} archivos en {FILES_ROOT}:\n")
    for source, destination in moves:
        print(f"  {source.name}  ->  {destination.relative_to(FILES_ROOT)}")
        if apply_changes:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
    if not apply_changes:
        print("\nNo se ha movido nada. Ejecuta con --apply para aplicar el plan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
