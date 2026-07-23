"""Tool contract from chapter 3: schema, prompt and strict validation."""
import json


class ToolCallError(Exception):
    """La respuesta del modelo no es una llamada a herramienta valida."""


# Esquema de ejemplo impreso en el capitulo 3
TOOL_SCHEMA = {
    "search_files": {
        "description": "Busca archivos por nombre en el directorio del proyecto",
        "params": {"query": "texto a buscar en el nombre del archivo"},
    },
    "read_file": {
        "description": "Lee el contenido de un archivo de texto",
        "params": {"path": "ruta del archivo a leer"},
    },
}


def build_tools_prompt(schema: dict) -> str:
    lines = ["Herramientas disponibles:"]
    for name, spec in schema.items():
        params = ", ".join(spec["params"].keys())
        lines.append(f"- {name}({params}): {spec['description']}")
    return "\n".join(lines)


def validate_call(raw: str, schema: dict) -> dict:
    try:
        call = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ToolCallError(f"JSON invalido: {exc}") from exc

    if "tool" not in call:
        raise ToolCallError("Falta la clave 'tool' en la respuesta")

    tool_name = call["tool"]
    if tool_name not in schema:
        raise ToolCallError(f"Herramienta desconocida: {tool_name}")

    return call
