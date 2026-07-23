"""BaseAgent from chapter 3: the reusable pattern behind the ten agents.

Cada herramienta se registra como: {"nombre": {"description": ..., "params":
{...}, "func": funcion_python}}. El libro imprime run(); _chat y
_execute_and_finish son los dos metodos que el capitulo deja "para el
repositorio".
"""
import json
import os

import ollama
from dotenv import load_dotenv

from .tools import ToolCallError, build_tools_prompt, validate_call

load_dotenv()


class BaseAgent:
    model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    system_prompt: str = ""
    tools: dict = {}

    def run(self, question: str, max_retries: int = 2) -> str:
        messages = [
            {"role": "system", "content": self._full_system_prompt()},
            {"role": "user", "content": question},
        ]
        for _ in range(max_retries + 1):
            content = self._chat(messages)
            try:
                call = validate_call(content, self.tools)
            except ToolCallError as exc:
                # Respuesta en texto normal: no era una llamada a herramienta
                if not content.lstrip().startswith("{"):
                    return content
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Error: {exc}"})
                continue
            return self._execute_and_finish(call, messages)
        return "No se pudo obtener una respuesta valida tras varios intentos."

    def _full_system_prompt(self) -> str:
        if not self.tools:
            return self.system_prompt
        return self.system_prompt + "\n\n" + build_tools_prompt(self.tools)

    def _chat(self, messages: list) -> str:
        return ollama.chat(model=self.model, messages=messages)["message"]["content"]

    def _execute_and_finish(self, call: dict, messages: list) -> str:
        func = self.tools[call["tool"]]["func"]
        result = func(**call.get("params", {}))
        messages.append({"role": "assistant", "content": json.dumps(call)})
        messages.append({"role": "user", "content": f"Resultado: {result}"})
        return self._chat(messages)
