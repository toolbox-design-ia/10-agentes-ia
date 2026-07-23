"""MCP server for the personal RAG agent (chapter 14).

El fragmento impreso en el capitulo, completo: la logica de busqueda es
exactamente la del agente del capitulo 4; lo unico nuevo es el decorador
@mcp.tool() y la linea que arranca el servidor por stdio.
"""
import sys
from pathlib import Path

# El servidor reutiliza el agente del capitulo 4: asegura la raiz en sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("rag-personal")


def retrieve_from_index(query: str, top_k: int) -> list[str]:
    # Carga del indice desde disco y busqueda: el codigo del capitulo 4
    import importlib

    brain = importlib.import_module("agents.01_second_brain.agent")
    if brain.get_collection().count() == 0:
        return ["El indice esta vacio: ejecuta antes el agente del "
                "capitulo 4 para indexar tus notas."]
    return [f"[{chunk_id}] {text}"
            for chunk_id, text in brain.retrieve(query, top_k=top_k)]


@mcp.tool()
def search_notes(query: str, top_k: int = 5) -> list[str]:
    """Busca en el indice vectorial personal y devuelve los fragmentos mas relevantes."""
    return retrieve_from_index(query, top_k)


if __name__ == "__main__":
    mcp.run(transport="stdio")
