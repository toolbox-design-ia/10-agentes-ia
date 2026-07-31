"""Fill-in-the-middle (chapter 11): completion that knows what comes after.

El error habitual al construir un copiloto local es tratar el autocompletado
como una conversacion: pedirle al modelo "continua este codigo" con todo el
archivo como prefijo. Ese enfoque ignora lo que viene DESPUES del cursor y
genera codigo que colisiona con lo ya escrito.

FIM entrega las dos mitades. Ollama expone el parametro `suffix` en
/api/generate y arma con el la plantilla de tokens especiales que el modelo
espera; por eso aqui no hay que escribir <|fim_prefix|> a mano, pero SI hay
que usar un modelo entrenado para FIM (qwen2.5-coder, deepseek-coder,
codellama 7b/13b). Un generalista ignora el sufijo.
"""
import os
import re

import ollama
from dotenv import load_dotenv

load_dotenv()

# Modelo pequeno y especializado: en FIM pesa mas la velocidad que el tamano
MODEL = os.getenv("COPILOT_FIM_MODEL", "qwen2.5-coder:1.5b")
# Lineas de contexto a cada lado del cursor. Recortar acelera la respuesta.
PREFIX_LINES = int(os.getenv("COPILOT_PREFIX_LINES", "60"))
SUFFIX_LINES = int(os.getenv("COPILOT_SUFFIX_LINES", "30"))
MAX_TOKENS = int(os.getenv("COPILOT_MAX_TOKENS", "96"))

# Algunos modelos cierran con un token de fin de archivo; se recorta ahi
_STOP_MARKERS = ("<|endoftext|>", "<|file_sep|>", "<|fim_pad|>", "<|repo_name|>")


def window(prefix: str, suffix: str) -> tuple[str, str]:
    # Solo N lineas a cada lado: el archivo entero satura el contexto y no
    # mejora la sugerencia, porque lo que importa esta junto al cursor
    prefix_lines = prefix.splitlines(keepends=True)
    suffix_lines = suffix.splitlines(keepends=True)
    return ("".join(prefix_lines[-PREFIX_LINES:]),
            "".join(suffix_lines[:SUFFIX_LINES]))


def clean(raw: str) -> str:
    for marker in _STOP_MARKERS:
        if marker in raw:
            raw = raw.split(marker, 1)[0]
    # Un modelo de chat puede envolver la respuesta en un bloque markdown
    fenced = re.search(r"```[a-zA-Z]*\n(.*?)```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    return raw.rstrip()


class ModelDoesNotSupportFIM(RuntimeError):
    """El modelo configurado no tiene plantilla de fill-in-the-middle."""


def complete(prefix: str, suffix: str, filename: str = "") -> str:
    """Devuelve el texto que rellena el hueco entre prefix y suffix."""
    near_prefix, near_suffix = window(prefix, suffix)
    if not near_prefix.strip():
        return ""
    try:
        response = ollama.generate(
            model=MODEL,
            prompt=near_prefix,
            suffix=near_suffix,
            options={
                "num_predict": MAX_TOKENS,
                "temperature": 0.1,   # completar codigo no es tarea creativa
                "stop": ["\n\n\n"],
            },
        )
    except ollama.ResponseError as exc:
        # Un generalista (llama3.1, mistral) no trae plantilla FIM y Ollama
        # responde 400 "does not support insert". Merece un mensaje claro.
        if "does not support insert" in str(exc):
            raise ModelDoesNotSupportFIM(
                f"El modelo '{MODEL}' no admite fill-in-the-middle. "
                "Usa uno entrenado para ello: qwen2.5-coder, deepseek-coder "
                "o codellama:7b/13b, y declaralo en COPILOT_FIM_MODEL."
            ) from exc
        raise
    return clean(response["response"])
