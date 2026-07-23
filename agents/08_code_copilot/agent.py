"""Code copilot (chapter 11): local model over your own files.

Le pasas un archivo y una instruccion; propone la version modificada y la
muestra como diff. Solo escribe en disco con --apply, y siempre deja una
copia .bak. Regla del capitulo: el copiloto propone, tu decides.
"""
import difflib
import os
import re
import shutil
import sys
from pathlib import Path

import ollama
from dotenv import load_dotenv

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def extract_code(raw: str) -> str:
    # Si el modelo envuelve el codigo en un bloque markdown, se extrae
    match = re.search(r"```[a-zA-Z]*\n(.*?)```", raw, re.DOTALL)
    return match.group(1) if match else raw


def propose(source: str, instruction: str, filename: str) -> str:
    prompt = (PROMPTS_DIR / "code_copilot.txt").read_text(encoding="utf-8")
    reply = ollama.generate(
        model=MODEL,
        prompt=prompt.format(filename=filename, instruction=instruction,
                             source=source),
    )["response"]
    return extract_code(reply)


def show_diff(before: str, after: str, filename: str) -> bool:
    diff = list(difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile=filename, tofile=filename + " (propuesta)", lineterm=""))
    if not diff:
        print("El modelo no propone cambios.")
        return False
    print("\n".join(diff))
    return True


def main() -> int:
    apply_changes = "--apply" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(args) < 2:
        print("Uso: python agent.py <archivo> \"instruccion\" [--apply]")
        print("Ej.:  python agent.py script.py \"anade manejo de errores\"")
        return 1
    path = Path(args[0])
    instruction = " ".join(args[1:])
    if not path.is_file():
        print(f"No existe el archivo {path}")
        return 1
    source = path.read_text(encoding="utf-8")
    print(f"Consultando al modelo ({MODEL})...")
    proposal = propose(source, instruction, path.name)
    if not show_diff(source, proposal, path.name):
        return 0
    if apply_changes:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        path.write_text(proposal, encoding="utf-8")
        print(f"\nAplicado. Copia de seguridad: {path.name}.bak")
    else:
        print("\nNo se ha tocado el archivo. Ejecuta con --apply para aplicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
