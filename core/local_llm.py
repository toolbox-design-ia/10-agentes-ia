"""LocalLLM: the generic interface described in the book's conclusions.

Cada agente puede llamar a esta interfaz en lugar de invocar a Ollama
directamente: sustituir un modelo por otro pasa a ser cambiar una entrada
de configuracion, no editar diez archivos.
"""
import os

import ollama
from dotenv import load_dotenv

load_dotenv()


class LocalLLM:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    def generate(self, prompt: str, model: str | None = None,
                 temperature: float = 0.7) -> str:
        response = ollama.generate(
            model=model or self.model,
            prompt=prompt,
            options={"temperature": temperature},
        )
        return response["response"]
