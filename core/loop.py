"""Agent loop from chapter 3: validation, retry and tool execution.

El capitulo imprime run_with_retry(question, schema); aqui la version
completa recibe ademas `functions` (nombre -> funcion Python) porque el
fragmento del libro asume ese registro definido mas arriba en el capitulo.
"""
import json
import os

import ollama
from dotenv import load_dotenv

from .tools import ToolCallError, validate_call

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

SYSTEM_PROMPT = """Respondes usando herramientas cuando las necesitas.
Si necesitas una herramienta, responde SOLO con JSON:
{"tool": "nombre_herramienta", "params": {}}
Si no necesitas ninguna, responde en texto normal."""


def execute_and_finish(call: dict, messages: list, functions: dict) -> str:
    # Ejecuta la herramienta elegida y pide al modelo la respuesta final
    result = functions[call["tool"]](**call.get("params", {}))
    messages.append({"role": "assistant", "content": json.dumps(call)})
    messages.append({"role": "user", "content": f"Resultado: {result}"})
    final = ollama.chat(model=MODEL, messages=messages)
    return final["message"]["content"]


def run_with_retry(question: str, schema: dict, functions: dict,
                   max_retries: int = 2) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    for _ in range(max_retries + 1):
        content = ollama.chat(model=MODEL, messages=messages)["message"]["content"]
        try:
            call = validate_call(content, schema)
        except ToolCallError as exc:
            # Si no parece JSON, es una respuesta directa en texto normal
            if not content.lstrip().startswith("{"):
                return content
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user",
                             "content": f"Error: {exc}. Corrige el formato."})
            continue
        return execute_and_finish(call, messages, functions)
    return "No se pudo obtener una respuesta valida tras varios intentos."
