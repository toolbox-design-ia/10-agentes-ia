"""Web watcher (chapter 9): scrape responsable + alertas sin fatiga.

Los nombres de las funciones siguen exactamente los fragmentos impresos en
el capitulo (descargar, hash_contenido, extraer_texto_relevante...). El
capitulo imprime el clasificador con el modelo "mistral"; aqui el modelo se
lee del .env (OLLAMA_MODEL) para no obligar a descargar otro.
"""
import difflib
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
STATE_DIR = Path("data/web_watcher")

HEADERS = {"User-Agent": "MiAgenteMonitor/1.0 (contacto@midominio.com)"}


def descargar(url: str) -> str:
    respuesta = requests.get(url, headers=HEADERS, timeout=10)
    respuesta.raise_for_status()
    return respuesta.text


def hash_contenido(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def extraer_texto_relevante(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for etiqueta in soup(["script", "style", "svg"]):
        etiqueta.decompose()
    bloques = soup.find_all(["h1", "h2", "h3", "p", "li", "span"])
    return "\n".join(b.get_text(strip=True) for b in bloques if b.get_text(strip=True))


def diferencias(bloques_antes: list[str], bloques_ahora: list[str]) -> list[str]:
    return list(difflib.unified_diff(bloques_antes, bloques_ahora, lineterm=""))


def puede_rastrear(url_base: str, ruta: str, user_agent: str) -> bool:
    rp = RobotFileParser()
    rp.set_url(f"{url_base}/robots.txt")
    try:
        rp.read()
    except OSError:
        return True  # sin robots.txt accesible: se asume permitido
    return rp.can_fetch(user_agent, ruta)


def descargar_con_backoff(url: str, intentos_max: int = 5) -> str:
    espera = 1
    for _intento in range(intentos_max):
        respuesta = requests.get(url, headers=HEADERS, timeout=10)
        if respuesta.status_code != 429:
            respuesta.raise_for_status()
            return respuesta.text
        time.sleep(espera)
        espera *= 2
    raise RuntimeError(f"El sitio sigue rechazando la solicitud tras {intentos_max} intentos")


def es_cambio_relevante(diff: str, criterio: str) -> bool:
    prompt = (
        f"Este es un fragmento de diff entre dos versiones de una pagina web:\n\n{diff}\n\n"
        f"Criterio de relevancia del usuario: {criterio}\n"
        "Responde solo 'si' o 'no': el cambio es relevante segun ese criterio?"
    )
    respuesta = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    texto = respuesta.json()["response"].strip().lower()
    return texto.startswith("s")


def notificar(titulo: str, mensaje: str) -> None:
    subprocess.run(["notify-send", titulo, mensaje], check=False)


def estado_de(url: str) -> Path:
    return STATE_DIR / (hashlib.sha1(url.encode()).hexdigest()[:12] + ".json")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print("Uso: python agent.py <url> [criterio de relevancia]")
        print("Ej.:  python agent.py https://ejemplo.com/precios 'cambios de precio'")
        return 1
    url = args[0]
    criterio = " ".join(args[1:]) or "cualquier cambio de contenido"
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if not puede_rastrear(base, parsed.path or "/", HEADERS["User-Agent"]):
        print(f"robots.txt de {base} no permite rastrear esa ruta. Se respeta.")
        return 1
    html = descargar_con_backoff(url)
    bloques_ahora = extraer_texto_relevante(html).split("\n")
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = estado_de(url)
    if not state_file.exists():
        state_file.write_text(json.dumps({"url": url, "bloques": bloques_ahora},
                                         ensure_ascii=False), encoding="utf-8")
        print("Primera visita: estado guardado. Vuelve a ejecutar para comparar.")
        return 0
    bloques_antes = json.loads(state_file.read_text(encoding="utf-8"))["bloques"]
    diff = diferencias(bloques_antes, bloques_ahora)
    state_file.write_text(json.dumps({"url": url, "bloques": bloques_ahora},
                                     ensure_ascii=False), encoding="utf-8")
    if not diff:
        print("Sin cambios.")
        return 0
    diff_text = "\n".join(diff[:80])
    if es_cambio_relevante(diff_text, criterio):
        print(f"CAMBIO RELEVANTE en {url}:\n\n{diff_text}")
        notificar("Cambio relevante", url)
    else:
        print("La pagina cambio, pero el cambio no cumple tu criterio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
