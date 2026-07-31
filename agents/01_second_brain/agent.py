"""Second brain (chapter 4): local RAG over your own notes.

Indexa tus notas (.md y .txt) en una base vectorial local (ChromaDB) con
embeddings de Ollama, y responde preguntas citando los fragmentos usados.
Todo ocurre en tu maquina: nada sale de ella.
"""
import os
import sys
from pathlib import Path

import chromadb
import ollama
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.base_agent import BaseAgent  # noqa: E402

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
NOTES_DIR = Path(os.getenv("NOTES_DIR", "data/notes"))
INDEX_DIR = Path("data/second_brain_index")
CHUNK_SIZE = 800  # caracteres por fragmento (parrafos agrupados)

ANSWER_PROMPT = """Responde a la pregunta usando SOLO estos fragmentos de las
notas del usuario. Si la respuesta no esta en los fragmentos, dilo claramente.

Fragmentos:
{context}

Pregunta: {question}
"""


def load_chunks(root: Path) -> list[tuple[str, str]]:
    # Divide cada nota en fragmentos de ~CHUNK_SIZE caracteres por parrafos
    chunks = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in (".md", ".txt"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        buffer = ""
        part = 0
        for paragraph in text.split("\n\n"):
            if len(buffer) + len(paragraph) > CHUNK_SIZE and buffer:
                chunks.append((f"{path.name}#{part}", buffer.strip()))
                part += 1
                buffer = ""
            buffer += paragraph + "\n\n"
        if buffer.strip():
            chunks.append((f"{path.name}#{part}", buffer.strip()))
    return chunks


def embed(text: str) -> list[float]:
    return ollama.embeddings(model=EMBED_MODEL, prompt=text)["embedding"]


def get_collection():
    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    return client.get_or_create_collection("second_brain")


def build_index() -> int:
    chunks = load_chunks(NOTES_DIR)
    if not chunks:
        print(f"No hay notas .md/.txt en {NOTES_DIR} (variable NOTES_DIR del .env).")
        return 0
    collection = get_collection()
    for chunk_id, text in chunks:
        collection.upsert(ids=[chunk_id], documents=[text],
                          embeddings=[embed(text)])
    return len(chunks)


def retrieve(question: str, top_k: int = 4) -> list[tuple[str, str]]:
    collection = get_collection()
    result = collection.query(query_embeddings=[embed(question)],
                              n_results=min(top_k, max(collection.count(), 1)))
    return list(zip(result["ids"][0], result["documents"][0]))


def answer(question: str) -> str:
    hits = retrieve(question)
    context = "\n\n".join(f"[{cid}]\n{text}" for cid, text in hits)
    prompt = ANSWER_PROMPT.format(context=context, question=question)
    reply = ollama.generate(model=MODEL, prompt=prompt)["response"].strip()
    sources = ", ".join(cid for cid, _ in hits)
    return f"{reply}\n\nFuentes: {sources}"


def main() -> int:
    if "--reindex" in sys.argv or get_collection().count() == 0:
        print(f"Indexando notas de {NOTES_DIR} ...")
        total = build_index()
        print(f"Fragmentos indexados: {total}")
        if total == 0:
            return 1
    print("Segundo cerebro listo. Pregunta (Enter vacio para salir).")
    while True:
        question = input("\n> ").strip()
        if not question:
            return 0
        print("\n" + answer(question))

# ---------------------------------------------------------------------------
# El patron del capitulo 3: este agente expuesto como herramientas
# ---------------------------------------------------------------------------

def tool_search_notes(question: str) -> str:
    hits = retrieve(question)
    if not hits:
        return "El indice no tiene fragmentos relevantes para esa pregunta."
    return "\n\n".join(f"[{cid}] {text[:400]}" for cid, text in hits)


def tool_reindex() -> str:
    return f"Fragmentos indexados: {build_index()}"


class SecondBrainAgent(BaseAgent):
    """Capitulo 4 sobre el patron del capitulo 3."""

    system_prompt = (
        "Respondes preguntas sobre las notas personales del usuario. "
        "Usa search_notes para recuperar fragmentos ANTES de responder, y "
        "cita entre corchetes el identificador de cada fragmento que uses. "
        "Si los fragmentos no contienen la respuesta, dilo claramente."
    )
    tools = {
        "search_notes": {
            "description": "Busca en el indice vectorial de notas del usuario",
            "params": {"question": "pregunta o terminos a buscar"},
            "func": tool_search_notes,
        },
        "reindex": {
            "description": "Reconstruye el indice desde la carpeta de notas",
            "params": {},
            "func": tool_reindex,
        },
    }


if __name__ == "__main__":
    sys.exit(main())
