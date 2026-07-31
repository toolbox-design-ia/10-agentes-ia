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

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.base_agent import BaseAgent  # noqa: E402

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

# ---------------------------------------------------------------------------
# El patron del capitulo 3: este agente expuesto como herramientas
# ---------------------------------------------------------------------------

def tool_propose_change(path: str, instruction: str) -> str:
    archivo = Path(path)
    if not archivo.is_file():
        return f"No existe el archivo {archivo}."
    origen = archivo.read_text(encoding="utf-8")
    propuesta = propose(origen, instruction, archivo.name)
    diff = list(difflib.unified_diff(origen.splitlines(), propuesta.splitlines(),
                                     fromfile=archivo.name,
                                     tofile=archivo.name + " (propuesta)",
                                     lineterm=""))
    return "\n".join(diff) if diff else "El modelo no propone cambios."


def tool_complete_here(path: str, line: int, character: int = 0) -> str:
    import importlib
    fim = importlib.import_module("agents.08_code_copilot.fim")
    texto = Path(path).read_text(encoding="utf-8")
    lineas = texto.splitlines(keepends=True)
    corte = sum(len(l) for l in lineas[: int(line)]) + int(character)
    return fim.complete(texto[:corte], texto[corte:], Path(path).name) or "(sin sugerencia)"


def tool_run_tests(path: str, tests: str, instruction: str = "haz que pasen los tests") -> str:
    import importlib
    runner = importlib.import_module("agents.08_code_copilot.test_runner")
    informe = runner.repair_until_green(Path(path), Path(tests), instruction)
    lineas = [f"intento {a.number}: {'PASA' if a.passed else 'FALLA'} — {a.summary}"
              for a in informe.attempts]
    return ("Tests en verde.\n" if informe.passed else "Sin converger.\n") + "\n".join(lineas)


class CodeCopilotAgent(BaseAgent):
    """Capitulo 11 sobre el patron del capitulo 3."""

    system_prompt = (
        "Ayudas a modificar codigo. Propones cambios como diff con "
        "propose_change, completas huecos con complete_here y verificas con "
        "run_tests. NUNCA escribes en los archivos del usuario: el copiloto "
        "propone, la persona decide."
    )
    tools = {
        "propose_change": {
            "description": "Propone un cambio sobre un archivo y lo muestra como diff",
            "params": {"path": "ruta del archivo", "instruction": "que hay que cambiar"},
            "func": tool_propose_change,
        },
        "complete_here": {
            "description": "Completa el hueco en una posicion del archivo (FIM)",
            "params": {"path": "ruta del archivo", "line": "numero de linea (desde 0)",
                       "character": "columna"},
            "func": tool_complete_here,
        },
        "run_tests": {
            "description": "Ejecuta pytest y corrige el codigo hasta que pase",
            "params": {"path": "archivo a corregir", "tests": "archivo de tests",
                       "instruction": "que se quiere conseguir"},
            "func": tool_run_tests,
        },
    }


if __name__ == "__main__":
    sys.exit(main())
