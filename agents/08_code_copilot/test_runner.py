"""Test runner agent (chapter 11): from a suggestion to a verified patch.

Un modelo de lenguaje, por bien afinado que este para codigo, no ejecuta lo
que escribe. Puede proponer una funcion que compila pero falla en un caso
limite. Este mini-agente cierra el bucle: aplica la propuesta sobre una copia
de trabajo, ejecuta pytest, lee el fallo real y le pide al modelo que corrija
su propio codigo con esa evidencia delante.

Es el bucle de percepcion-accion-ajuste del capitulo 3, con una diferencia
importante: la senal de vuelta no es el juicio del modelo sobre si mismo, es
el codigo de salida de pytest.

El original NUNCA se modifica hasta que los tests pasan y quien ejecuta lo
aprueba: todo el ciclo ocurre en un directorio temporal.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import ollama
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("COPILOT_REPAIR_MODEL", os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b"))
PYTEST_TIMEOUT = int(os.getenv("COPILOT_PYTEST_TIMEOUT", "120"))

REPAIR_PROMPT = """Este archivo Python no pasa sus tests.

Archivo: {filename}

```python
{source}
```

Salida de pytest:

```
{failure}
```

Instruccion: {instruction}

Devuelve el archivo COMPLETO corregido dentro de un unico bloque de codigo
markdown. No expliques nada fuera del bloque.
"""


@dataclass
class Attempt:
    number: int
    passed: bool
    summary: str


@dataclass
class RepairReport:
    passed: bool
    attempts: list[Attempt] = field(default_factory=list)
    final_source: str = ""
    last_output: str = ""

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "attempts": [{"number": a.number, "passed": a.passed,
                          "summary": a.summary} for a in self.attempts],
            "finalSource": self.final_source,
            "lastOutput": self.last_output[-4000:],
        }


def extract_code(raw: str) -> str:
    match = re.search(r"```[a-zA-Z]*\n(.*?)```", raw, re.DOTALL)
    return match.group(1) if match else raw


def summarize(output: str) -> str:
    # La ultima linea util de pytest es su resumen: "1 failed, 2 passed in..."
    for line in reversed(output.strip().splitlines()):
        if re.search(r"\b(passed|failed|error)\b", line):
            return line.strip("= ").strip()
    return output.strip().splitlines()[-1] if output.strip() else "sin salida"


def run_pytest(workdir: Path, tests_name: str) -> tuple[bool, str]:
    """Ejecuta pytest acotado al archivo de tests. Devuelve (verde, salida)."""
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", tests_name, "-x", "-q", "--no-header"],
            cwd=workdir, capture_output=True, text=True, timeout=PYTEST_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, f"pytest supero el limite de {PYTEST_TIMEOUT}s (bucle infinito?)"
    return completed.returncode == 0, completed.stdout + completed.stderr


def propose_fix(source: str, failure: str, filename: str, instruction: str) -> str:
    reply = ollama.generate(
        model=MODEL,
        prompt=REPAIR_PROMPT.format(filename=filename, source=source,
                                    failure=failure[-3000:], instruction=instruction),
        options={"temperature": 0.1, "num_predict": 1024},
    )["response"]
    return extract_code(reply)


def repair_until_green(source_path: Path, tests_path: Path, instruction: str,
                       max_attempts: int = 3,
                       initial_source: str | None = None) -> RepairReport:
    """Aplica, ejecuta y corrige hasta que los tests pasen o se agoten los intentos."""
    report = RepairReport(passed=False)
    source = initial_source if initial_source is not None else source_path.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="copiloto-") as tmp:
        workdir = Path(tmp)
        # Copia de trabajo: el proyecto real no se toca en ningun momento
        shutil.copy2(tests_path, workdir / tests_path.name)
        work_source = workdir / source_path.name

        for attempt in range(1, max_attempts + 1):
            work_source.write_text(source, encoding="utf-8")
            green, output = run_pytest(workdir, tests_path.name)
            report.attempts.append(Attempt(attempt, green, summarize(output)))
            report.last_output = output
            if green:
                report.passed = True
                report.final_source = source
                return report
            if attempt == max_attempts:
                break
            # Hay fallo y quedan intentos: se le devuelve el traceback al modelo
            fixed = propose_fix(source, output, source_path.name, instruction)
            if not fixed.strip() or fixed.strip() == source.strip():
                break  # el modelo no propone nada nuevo: no insistimos
            source = fixed

    report.final_source = source
    return report


def main() -> int:
    if len(sys.argv) < 3:
        print("Uso: python test_runner.py <archivo.py> <test_archivo.py> [instruccion]")
        return 1
    source_path, tests_path = Path(sys.argv[1]), Path(sys.argv[2])
    instruction = " ".join(sys.argv[3:]) or "haz que pasen los tests"
    report = repair_until_green(source_path, tests_path, instruction)
    for attempt in report.attempts:
        estado = "PASA" if attempt.passed else "FALLA"
        print(f"  intento {attempt.number}: {estado} — {attempt.summary}")
    if report.passed:
        print("\nTests en verde. Propuesta final:\n")
        print(report.final_source)
        print("\n(El archivo original no se ha tocado.)")
    else:
        print(f"\nSin converger tras {len(report.attempts)} intentos. "
              "Ultimo error:\n")
        print(report.last_output[-1500:])
    return 0 if report.passed else 2


if __name__ == "__main__":
    sys.exit(main())
