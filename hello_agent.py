"""Hola, agente — la prueba de vida del capitulo 3 (impresa integra en el libro)."""
import os
import sys

import ollama
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


def ask(question: str) -> str:
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": question}],
    )
    return response["message"]["content"].strip()


def validate(answer: str) -> bool:
    return isinstance(answer, str) and len(answer) > 0


if __name__ == "__main__":
    pregunta = "¿Que es un agente de IA, en una frase?"
    respuesta = ask(pregunta)

    if not validate(respuesta):
        print("El modelo no devolvio una respuesta valida. Revisa el Anexo B.")
        sys.exit(1)

    print(f"Pregunta: {pregunta}")
    print(f"Respuesta: {respuesta}")
