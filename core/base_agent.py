"""BaseAgent from chapter 3: the reusable pattern behind the ten agents.

Cada herramienta se registra como: {"nombre": {"description": ..., "params":
{...}, "func": funcion_python}}. El libro imprime run(); _chat y
_execute_and_finish son los dos metodos que el capitulo deja "para el
repositorio".

El bucle es multipaso: el modelo puede encadenar varias herramientas en un
mismo turno, y termina cuando responde en texto normal en lugar de pedir otra.
"""
import json
import os
import re

import ollama
from dotenv import load_dotenv

from .tools import ToolCallError, build_tools_prompt, validate_call

load_dotenv()


class BaseAgent:
    model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    system_prompt: str = ""
    tools: dict = {}
    max_steps: int = 5  # tope de herramientas encadenadas en un mismo turno

    # El contrato JSON del capitulo 3: sin esto, el modelo responde en prosa
    # describiendo lo que haria, y la herramienta no se ejecuta nunca.
    TOOL_CONTRACT = (
        "Cuando necesites una herramienta, responde SOLO con un objeto JSON, "
        "sin texto antes ni despues y sin bloques de codigo markdown:\n"
        '{"tool": "nombre_herramienta", "params": {"nombre": "valor"}}\n'
        "Cuando ya tengas el resultado de la herramienta, responde al usuario "
        "en texto normal, sin JSON.\n"
        "Nunca describas lo que vas a hacer: hazlo llamando a la herramienta."
    )

    def run(self, question: str, max_retries: int = 2) -> str:
        messages = [
            {"role": "system", "content": self._full_system_prompt()},
            {"role": "user", "content": question},
        ]
        for _step in range(self.max_steps):
            call = self._next_call(messages, max_retries)
            if call is None:
                # El modelo respondio en texto normal: el turno ha terminado
                return messages[-1]["content"]
            if isinstance(call, str):
                return call  # se agotaron los reintentos
            result = self._execute(call)
            messages.append({"role": "assistant", "content": json.dumps(call)})
            messages.append({"role": "user",
                             "content": f"Resultado de {call['tool']}: {result}\n\n"
                                        "Responde ahora al usuario en texto normal."})
        return ("El agente encadeno demasiadas herramientas sin llegar a una "
                "respuesta. Prueba con una peticion mas concreta.")

    def _next_call(self, messages: list, max_retries: int):
        """Devuelve la llamada validada, None si fue texto normal, o el mensaje de fallo."""
        for _ in range(max_retries + 1):
            content = self._chat(messages)
            candidate = self._unwrap(content)
            if not candidate.lstrip().startswith("{"):
                messages.append({"role": "assistant", "content": content})
                return None
            try:
                return validate_call(candidate, self.tools)
            except ToolCallError as exc:
                disponibles = ", ".join(self.tools)
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user",
                                 "content": f"Error: {exc}. Herramientas disponibles: "
                                            f"{disponibles}. Corrige el formato."})
        return "No se pudo obtener una respuesta valida tras varios intentos."

    def _execute(self, call: dict) -> str:
        func = self.tools[call["tool"]]["func"]
        try:
            return str(func(**call.get("params", {})))
        except TypeError as exc:
            # Parametros que no encajan con la firma: se lo decimos al modelo
            return f"ERROR de parametros: {exc}"
        except Exception as exc:
            return f"ERROR al ejecutar {call['tool']}: {exc}"

    def _full_system_prompt(self) -> str:
        if not self.tools:
            return self.system_prompt
        return "\n\n".join([self.system_prompt,
                            build_tools_prompt(self.tools),
                            self.TOOL_CONTRACT])

    def _chat(self, messages: list) -> str:
        return ollama.chat(model=self.model, messages=messages)["message"]["content"]

    # Compatibilidad con el fragmento impreso en el capitulo 3
    def _execute_and_finish(self, call: dict, messages: list) -> str:
        result = self._execute(call)
        messages.append({"role": "assistant", "content": json.dumps(call)})
        messages.append({"role": "user", "content": f"Resultado: {result}"})
        return self._chat(messages)

    @staticmethod
    def _unwrap(content: str) -> str:
        """Quita el bloque markdown con el que algunos modelos envuelven el JSON."""
        texto = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
        return fenced.group(1) if fenced else texto
