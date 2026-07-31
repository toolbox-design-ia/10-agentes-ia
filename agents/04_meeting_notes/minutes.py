"""Structured minutes (chapter 7): two passes, schema validation, retry.

La primera pasada es permisiva: recorre la transcripcion y saca CANDIDATOS a
decision o tarea, sin preocuparse del formato. Es mejor capturar de mas que
perder un acuerdo real por ceirse a un patron estricto.

La segunda pasada es estricta: normaliza esos candidatos contra un esquema
Pydantic. Si un campo obligatorio falta o el tipo no encaja, el error de
validacion vuelve al modelo y se reintenta; agotados los intentos, el agente
lo dice en lugar de entregar un acta a medias.

Lo que el modelo no puede saber, queda vacio: si nadie dijo quien se encarga
de una tarea, el responsable es None y el acta lo marca para revision humana.
"""
import json
import os
import re

import ollama
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
MAX_RETRIES = int(os.getenv("MINUTES_MAX_RETRIES", "2"))
CHUNK_CHARS = int(os.getenv("MINUTES_CHUNK_CHARS", "6000"))


# ----------------------------- el esquema -----------------------------
class Task(BaseModel):
    description: str = Field(min_length=3)
    owner: str | None = None      # None = nadie lo dijo; no se inventa
    due: str | None = None


class Minutes(BaseModel):
    summary: str = Field(min_length=3)
    decisions: list[str] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lineas = ["## Resumen", self.summary, "", "## Decisiones"]
        lineas += [f"- {d}" for d in self.decisions] or ["- Ninguna registrada"]
        lineas += ["", "## Tareas"]
        if not self.tasks:
            lineas.append("- Ninguna registrada")
        for t in self.tasks:
            quien = t.owner or "sin asignar"
            plazo = f" (plazo: {t.due})" if t.due else ""
            lineas.append(f"- [{quien}] {t.description}{plazo}")
        pendientes = [t for t in self.tasks if not t.owner]
        if pendientes:
            lineas += ["", f"> {len(pendientes)} tarea(s) sin responsable explicito: "
                           "revisalas antes de repartir el acta."]
        return "\n".join(lineas)


CANDIDATES_PROMPT = """Lee esta transcripcion de una reunion y extrae, en bruto,
las frases que contengan una DECISION ("decidimos", "acordamos", "aprobamos",
"queda claro que") o una TAREA asignada ("se encarga de", "el responsable es",
"quedamos en que X hara").

Copia las frases tal cual aparecen, una por linea, sin numerar y sin comentarlas.
Es mejor sobrar que faltar: ante la duda, incluye la frase.
Si no hay ninguna, responde exactamente: NINGUNA

Transcripcion:
{transcript}
"""

STRUCTURE_PROMPT = """Convierte estos candidatos en un objeto JSON con esta forma
EXACTA, sin texto alrededor y sin bloque markdown:

{{"summary": "3-5 frases con lo esencial de la reunion",
  "decisions": ["decision 1", "decision 2"],
  "tasks": [{{"description": "que hay que hacer", "owner": "quien o null",
             "due": "plazo o null"}}]}}

Reglas:
- No inventes nada que no este en el material.
- Si el responsable de una tarea no se menciona, owner debe ser null.
- Si no se menciona plazo, due debe ser null.
- decisions y tasks pueden ser listas vacias.

Resumen de la reunion (transcripcion):
{transcript}

Candidatos detectados en la primera pasada:
{candidates}
"""


def _generate(prompt: str, json_mode: bool = False) -> str:
    kwargs = {"model": MODEL, "prompt": prompt, "options": {"temperature": 0.1}}
    if json_mode:
        # Ollama restringe la generacion a JSON sintacticamente valido
        kwargs["format"] = "json"
    return ollama.generate(**kwargs)["response"].strip()


def extract_candidates(transcript: str) -> str:
    """Primera pasada, permisiva: frases que suenan a decision o a tarea."""
    trozos = [transcript[i:i + CHUNK_CHARS]
              for i in range(0, len(transcript), CHUNK_CHARS)] or [""]
    salida = []
    for trozo in trozos:
        bruto = _generate(CANDIDATES_PROMPT.format(transcript=trozo))
        if bruto.strip().upper() != "NINGUNA":
            salida.append(bruto.strip())
    return "\n".join(salida)


def _unwrap_json(raw: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fenced:
        return fenced.group(1)
    llave = re.search(r"\{.*\}", raw, re.DOTALL)
    return llave.group(0) if llave else raw


def structure(transcript: str, candidates: str,
              max_retries: int = MAX_RETRIES) -> Minutes:
    """Segunda pasada, estricta: valida contra el esquema y reintenta si falla."""
    prompt = STRUCTURE_PROMPT.format(transcript=transcript[:CHUNK_CHARS],
                                     candidates=candidates or "(ninguno)")
    ultimo_error = ""
    for intento in range(max_retries + 1):
        crudo = _generate(prompt if intento == 0 else
                          f"{prompt}\n\nTu respuesta anterior no valido. "
                          f"Error: {ultimo_error}\nDevuelve SOLO el JSON corregido.",
                          json_mode=True)
        try:
            return Minutes.model_validate_json(_unwrap_json(crudo))
        except (ValidationError, ValueError) as exc:
            ultimo_error = str(exc)[:400]
    raise ValueError(f"El modelo no produjo un acta valida tras "
                     f"{max_retries + 1} intentos. Ultimo error: {ultimo_error}")


def build_minutes(transcript: str) -> Minutes:
    """Las dos pasadas, en orden."""
    return structure(transcript, extract_candidates(transcript))
