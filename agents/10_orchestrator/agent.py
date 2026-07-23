"""Orchestrator (chapter 13): one model routing requests to the team.

Los nombres (orquestar, ejecutar_herramienta, registrar_traza,
liberar_modelo) y los contratos de herramienta siguen los fragmentos
impresos en el capitulo. Cada descripcion dice tambien lo que el agente NO
hace: el contrato es la primera barrera de seguridad.
"""
import importlib
import json
import os
import sys
import time
from pathlib import Path

import ollama
from dotenv import load_dotenv

# El orquestador importa a los demas agentes: asegura la raiz en sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

load_dotenv()
ORCHESTRATOR_MODEL = os.getenv("ORCHESTRATOR_MODEL", "qwen2.5:14b-instruct")
TRACES_FILE = REPO_ROOT / "traces" / "orquestador.jsonl"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "secretario_correo",
            "description": (
                "Procesa la bandeja de entrada local. Puede filtrar, "
                "clasificar y resumir correos. NO envia correos ni "
                "responde en nombre del usuario: solo lee y organiza."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "accion": {"type": "string",
                               "enum": ["filtrar", "resumir", "clasificar"],
                               "description": "operacion a realizar"},
                    "filtro": {"type": "string",
                               "description": "criterio de busqueda, ej. 'con adjuntos esta semana'"},
                },
                "required": ["accion"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lector_facturas",
            "description": (
                "Extrae importe, fecha de emision y vencimiento de facturas "
                "en PDF o imagen usando vision. NO agenda pagos ni contacta "
                "al emisor."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "rutas": {"type": "array", "items": {"type": "string"},
                              "description": "rutas de archivos PDF o imagenes de facturas"},
                },
                "required": ["rutas"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "segundo_cerebro",
            "description": (
                "Busca en las notas personales indexadas y responde con "
                "fragmentos citados. NO accede a internet."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pregunta": {"type": "string",
                                 "description": "pregunta sobre las notas del usuario"},
                },
                "required": ["pregunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vigia_web",
            "description": (
                "Comprueba si una pagina web cambio desde la ultima visita. "
                "NO rellena formularios ni interactua con el sitio."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL a vigilar"},
                    "criterio": {"type": "string",
                                 "description": "que tipo de cambio interesa"},
                },
                "required": ["url"],
            },
        },
    },
]


def ejecutar_herramienta(nombre: str, argumentos: dict) -> dict:
    if nombre == "secretario_correo":
        mail = importlib.import_module("agents.03_mail_clerk.agent")
        connection = mail.connect()
        try:
            messages = mail.fetch_unseen_headers(connection)
            labeled = [{"de": m["sender"], "asunto": m["subject"],
                        "clase": mail.classify(m)} for m in messages]
        finally:
            connection.logout()
        return {"sin_leer": len(labeled), "correos": labeled[:20]}
    if nombre == "lector_facturas":
        reader = importlib.import_module("agents.05_invoice_reader.read_invoices")
        results = []
        for ruta in argumentos.get("rutas", []):
            raw = reader.model_response(Path(ruta))
            invoice = reader.Invoice(**reader.extract_json(raw))
            results.append({"archivo": ruta, "proveedor": invoice.supplier,
                            "fecha": invoice.date, "total": invoice.total,
                            "avisos": reader.validate_invoice(invoice)})
        return {"facturas": results}
    if nombre == "segundo_cerebro":
        brain = importlib.import_module("agents.01_second_brain.agent")
        return {"respuesta": brain.answer(argumentos["pregunta"])}
    if nombre == "vigia_web":
        # Ejecucion en subproceso: el vigia es un script con estado propio
        import subprocess
        watcher = REPO_ROOT / "agents" / "06_web_watcher" / "agent.py"
        cmd = [sys.executable, str(watcher), argumentos["url"],
               argumentos.get("criterio", "")]
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return {"salida": run.stdout.strip()}
    raise ValueError(f"herramienta desconocida: {nombre}")


def registrar_traza(agente: str, argumentos: dict, resultado: dict,
                    duracion_s: float) -> None:
    entrada = {
        "agente": agente,
        "argumentos": argumentos,
        "resumen_resultado": str(resultado)[:200],
        "duracion_s": round(duracion_s, 2),
    }
    TRACES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")


def liberar_modelo(nombre_modelo: str) -> None:
    # keep_alive=0 descarga el modelo de la VRAM inmediatamente
    ollama.generate(model=nombre_modelo, prompt="", keep_alive=0)


def orquestar(peticion: str, max_rondas: int = 6) -> str:
    mensajes = [{"role": "user", "content": peticion}]
    for _ in range(max_rondas):
        respuesta = ollama.chat(model=ORCHESTRATOR_MODEL, messages=mensajes,
                                tools=TOOLS)["message"]
        llamadas = respuesta.get("tool_calls") or []
        if not llamadas:
            return respuesta["content"]
        mensajes.append(respuesta)
        for llamada in llamadas:
            nombre = llamada["function"]["name"]
            argumentos = llamada["function"]["arguments"]
            inicio = time.monotonic()
            try:
                resultado = ejecutar_herramienta(nombre, argumentos)
            except Exception as exc:  # la traza registra tambien los fallos
                resultado = {"error": str(exc)}
            registrar_traza(nombre, argumentos, resultado,
                            time.monotonic() - inicio)
            mensajes.append({"role": "tool",
                             "content": json.dumps(resultado, ensure_ascii=False)})
    return "El orquestador supero el limite de rondas sin respuesta final."


def main() -> int:
    print(f"Orquestador ({ORCHESTRATOR_MODEL}). Los agentes disponibles y sus "
          "limites estan en los contratos del capitulo 13.")
    peticion = " ".join(sys.argv[1:]).strip() or input("\nPeticion: ").strip()
    if not peticion:
        return 0
    print("\n" + orquestar(peticion))
    print(f"\nTraza de la ejecucion: {TRACES_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
