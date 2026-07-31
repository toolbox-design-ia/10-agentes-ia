"""Researcher (chapter 10): multi-step investigation with cited sources.

El ciclo pensar-actuar-observar impreso en el capitulo, completo: busqueda
(DuckDuckGo, sin clave de API), lectura de paginas con trafilatura y
sintesis final que senala desacuerdos entre fuentes en vez de ocultarlos.
"""
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import ollama
import trafilatura
from bs4 import BeautifulSoup
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.base_agent import BaseAgent  # noqa: E402

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
HEADERS = {"User-Agent": "Mozilla/5.0 (investigador local; libro 10 agentes)"}
REPORTS_DIR = Path("data/research")


@dataclass
class Investigation:
    question: str
    steps: list[str] = field(default_factory=list)
    sources_read: list[dict] = field(default_factory=list)

    def history(self) -> str:
        return "\n".join(self.steps)


class LocalClient:
    """Envoltorio minimo sobre Ollama con la interfaz generate() del capitulo."""

    def generate(self, prompt: str) -> str:
        return ollama.generate(model=MODEL, prompt=prompt)["response"]


class Searcher:
    """Busqueda web sin clave de API (HTML de DuckDuckGo)."""

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        response = httpx.get("https://html.duckduckgo.com/html/",
                             params={"q": query}, headers=HEADERS,
                             timeout=15, follow_redirects=True)
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for link in soup.select("a.result__a")[:max_results]:
            results.append({"title": link.get_text(strip=True),
                            "url": link.get("href", "")})
        return results


def read_page(url: str, max_characters: int = 3000) -> str:
    html = httpx.get(url, timeout=10, follow_redirects=True).text
    text = trafilatura.extract(html) or ""
    return text[:max_characters]


PROMPT_REASONING = """Pregunta: {question}
Historial:
{history}

Responde con una sola linea, en uno de estos formatos exactos:
SEARCH: <consulta>
READ: <indice del resultado>
CONCLUDE: <tienes suficiente informacion>
"""


def next_step(client, investigation: Investigation) -> str:
    prompt = PROMPT_REASONING.format(
        question=investigation.question,
        history=investigation.history() or "(vacio)",
    )
    return client.generate(prompt).strip()


def investigate(client, searcher, question: str, max_steps: int = 8) -> Investigation:
    inv = Investigation(question=question)
    seen_results = []

    for _ in range(max_steps):
        step = next_step(client, inv)
        inv.steps.append(step)

        if step.startswith("SEARCH:"):
            query = step.removeprefix("SEARCH:").strip()
            seen_results = searcher.search(query)
            summary = "\n".join(
                f"[{i}] {r['title']} - {r['url']}"
                for i, r in enumerate(seen_results)
            )
            inv.steps.append(f"Resultados:\n{summary}")

        elif step.startswith("READ:"):
            try:
                index = int(step.removeprefix("READ:").strip().split()[0])
                url = seen_results[index]["url"]
            except (ValueError, IndexError):
                inv.steps.append("Error: indice de lectura no valido.")
                continue
            text = read_page(url)
            inv.sources_read.append({"url": url, "text": text})
            inv.steps.append(f"Contenido de [{index}]:\n{text[:800]}")

        elif step.startswith("CONCLUDE"):
            break

    return inv


PROMPT_SYNTHESIS = """Pregunta original: {question}

Fuentes consultadas:
{sources}

Redacta un informe breve que responda la pregunta. Si dos fuentes se
contradicen, senala el desacuerdo en vez de elegir una en silencio.
Cierra con una lista de fuentes citadas por numero.
"""


def synthesize(client, inv: Investigation) -> str:
    sources = "\n\n".join(
        f"[{i}] {f['url']}\n{f['text']}"
        for i, f in enumerate(inv.sources_read)
    )
    prompt = PROMPT_SYNTHESIS.format(question=inv.question, sources=sources)
    return client.generate(prompt)


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        question = input("Pregunta a investigar: ").strip()
    if not question:
        return 1
    client, searcher = LocalClient(), Searcher()
    print("Investigando (maximo 8 pasos)...")
    inv = investigate(client, searcher, question)
    if not inv.sources_read:
        print("No se pudo leer ninguna fuente. Revisa la conexion o "
              "reformula la pregunta.")
        return 1
    report = synthesize(client, inv)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "informe.md"
    out.write_text(f"# {question}\n\n{report}\n", encoding="utf-8")
    print(f"\n{report}\n\nInforme guardado en {out}")
    return 0

# ---------------------------------------------------------------------------
# El patron del capitulo 3: este agente expuesto como herramientas
# ---------------------------------------------------------------------------

def tool_search_web(query: str) -> str:
    resultados = Searcher().search(query)
    if not resultados:
        return "Sin resultados."
    return "\n".join(f"[{i}] {r['title']} — {r['url']}"
                     for i, r in enumerate(resultados))


def tool_read_url(url: str) -> str:
    return read_page(url) or "No se pudo extraer texto de esa pagina."


class ResearcherAgent(BaseAgent):
    """Capitulo 10 sobre el patron del capitulo 3."""

    system_prompt = (
        "Investigas preguntas cruzando varias fuentes web. Busca con "
        "search_web, lee con read_url, y cita siempre la URL de la que sale "
        "cada afirmacion. Si dos fuentes se contradicen, di el desacuerdo en "
        "vez de elegir una en silencio."
    )
    tools = {
        "search_web": {
            "description": "Busca en la web y devuelve titulos y URLs numerados",
            "params": {"query": "consulta de busqueda"},
            "func": tool_search_web,
        },
        "read_url": {
            "description": "Descarga una URL y devuelve su texto principal limpio",
            "params": {"url": "direccion a leer"},
            "func": tool_read_url,
        },
    }


if __name__ == "__main__":
    sys.exit(main())
