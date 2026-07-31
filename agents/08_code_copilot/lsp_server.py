"""Local LSP server (chapter 11): fill-in-the-middle completion over Ollama.

Habla Language Server Protocol por entrada y salida estandar, de modo que
cualquier editor que sea cliente LSP —VS Code, Neovim, Emacs, Helix— puede
usarlo sin un plugin propio. No sustituye al servidor de lenguaje nativo del
proyecto (pyright, tsserver): convive con el y solo anade sugerencias
generativas.

Dos capacidades:
  * textDocument/completion  -> completado FIM (prefijo + sufijo) con Ollama.
  * workspace/executeCommand -> codeCopilot.runTests, el ejecutor de tests
    del capitulo, que aplica una propuesta, corre pytest y pide al modelo
    que corrija su propio codigo cuando falla.

Disparo explicito por defecto: con un modelo local la latencia se mide en
segundos, no en milisegundos, asi que sugerir en cada tecla molesta mas de
lo que ayuda. Ver COMPLETION_TRIGGER en el .env y la seccion de latencia del
README de este agente.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import importlib

# El paquete empieza por digito, asi que no admite "import agents.08_...":
# importlib acepta el nombre como cadena y resuelve igual.
fim = importlib.import_module("agents.08_code_copilot.fim")
test_runner = importlib.import_module("agents.08_code_copilot.test_runner")

load_dotenv()

SERVER_NAME = "code-copilot-lsp"
SERVER_VERSION = "1.0.0"

# Disparo del completado: "explicit" (solo cuando el usuario lo pide) o
# "always" (tambien mientras escribe). Con un modelo local, "explicit".
COMPLETION_TRIGGER = os.getenv("COPILOT_COMPLETION_TRIGGER", "explicit")

LOG = os.getenv("COPILOT_LSP_LOG", "")


def log(message: str) -> None:
    # El canal de log no puede ser stdout: ahi viaja el protocolo
    if LOG:
        with open(LOG, "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    else:
        print(message, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# Transporte: JSON-RPC con cabecera Content-Length, tal como manda LSP
# --------------------------------------------------------------------------
def read_message(stream) -> dict | None:
    headers = {}
    while True:
        line = stream.readline()
        if not line:
            return None  # el editor cerro la tuberia
        line = line.decode("utf-8").strip()
        if not line:
            break  # linea vacia: terminan las cabeceras
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", 0))
    if not length:
        return None
    return json.loads(stream.read(length).decode("utf-8"))


def write_message(stream, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    stream.write(body)
    stream.flush()


# --------------------------------------------------------------------------
# Estado: los documentos abiertos, en memoria
# --------------------------------------------------------------------------
class Documents:
    def __init__(self) -> None:
        self._texts: dict[str, str] = {}

    def open(self, uri: str, text: str) -> None:
        self._texts[uri] = text

    def update(self, uri: str, text: str) -> None:
        self._texts[uri] = text

    def close(self, uri: str) -> None:
        self._texts.pop(uri, None)

    def text(self, uri: str) -> str:
        return self._texts.get(uri, "")

    def path(self, uri: str) -> Path:
        return Path(uri[7:] if uri.startswith("file://") else uri)


def offset_of(text: str, line: int, character: int) -> int:
    # LSP cuenta lineas y caracteres; el modelo necesita un corte en el texto
    lines = text.splitlines(keepends=True)
    return sum(len(l) for l in lines[:line]) + character


class CodeCopilotServer:
    def __init__(self) -> None:
        self.documents = Documents()
        self.running = True

    # ---------------- ciclo de vida ----------------
    def on_initialize(self, params: dict) -> dict:
        log(f"initialize desde {params.get('clientInfo', {}).get('name', '?')}")
        return {
            "capabilities": {
                # 1 = sincronizacion completa: el editor manda el texto entero
                "textDocumentSync": 1,
                "completionProvider": {
                    "resolveProvider": False,
                    "triggerCharacters": ["."] if COMPLETION_TRIGGER == "always" else [],
                },
                "executeCommandProvider": {
                    "commands": ["codeCopilot.runTests"],
                },
            },
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }

    def on_shutdown(self, params: dict) -> None:
        return None

    def on_exit(self, params: dict) -> None:
        self.running = False

    # ---------------- documentos ----------------
    def on_did_open(self, params: dict) -> None:
        doc = params["textDocument"]
        self.documents.open(doc["uri"], doc.get("text", ""))

    def on_did_change(self, params: dict) -> None:
        changes = params.get("contentChanges", [])
        if changes:
            # textDocumentSync=1: el ultimo cambio trae el documento completo
            self.documents.update(params["textDocument"]["uri"], changes[-1]["text"])

    def on_did_close(self, params: dict) -> None:
        self.documents.close(params["textDocument"]["uri"])

    # ---------------- completado FIM ----------------
    def on_completion(self, params: dict) -> dict:
        uri = params["textDocument"]["uri"]
        position = params["position"]
        text = self.documents.text(uri)
        cut = offset_of(text, position["line"], position["character"])

        invoked = params.get("context", {}).get("triggerKind", 1) == 1
        if COMPLETION_TRIGGER == "explicit" and not invoked:
            # El editor pregunto solo por escribir: con modelo local, no molestamos
            return {"isIncomplete": False, "items": []}

        started = time.monotonic()
        suggestion = fim.complete(
            prefix=text[:cut],
            suffix=text[cut:],
            filename=self.documents.path(uri).name,
        )
        elapsed = time.monotonic() - started
        log(f"completion {self.documents.path(uri).name} en {elapsed:.2f}s")

        if not suggestion.strip():
            return {"isIncomplete": False, "items": []}

        first_line = suggestion.strip().splitlines()[0][:60]
        return {
            "isIncomplete": False,
            "items": [{
                "label": first_line or "sugerencia",
                "kind": 15,  # Snippet
                "detail": f"copiloto local ({fim.MODEL}, {elapsed:.1f}s)",
                "documentation": suggestion,
                "insertText": suggestion,
                "textEdit": {
                    "range": {"start": position, "end": position},
                    "newText": suggestion,
                },
            }],
        }

    # ---------------- ejecutor de tests ----------------
    def on_execute_command(self, params: dict) -> dict:
        if params.get("command") != "codeCopilot.runTests":
            raise ValueError(f"comando desconocido: {params.get('command')}")
        args = (params.get("arguments") or [{}])[0]
        report = test_runner.repair_until_green(
            source_path=Path(args["path"]),
            tests_path=Path(args["tests"]),
            instruction=args.get("instruction", "haz que pasen los tests"),
            max_attempts=int(args.get("maxAttempts", 3)),
        )
        return report.as_dict()

    # ---------------- despacho ----------------
    HANDLERS = {
        "initialize": on_initialize,
        "shutdown": on_shutdown,
        "exit": on_exit,
        "textDocument/didOpen": on_did_open,
        "textDocument/didChange": on_did_change,
        "textDocument/didClose": on_did_close,
        "textDocument/completion": on_completion,
        "workspace/executeCommand": on_execute_command,
    }

    def serve(self, stdin, stdout) -> int:
        while self.running:
            message = read_message(stdin)
            if message is None:
                break
            method = message.get("method")
            handler = self.HANDLERS.get(method)
            if handler is None:
                if "id" in message:
                    write_message(stdout, {
                        "jsonrpc": "2.0", "id": message["id"],
                        "error": {"code": -32601, "message": f"metodo no soportado: {method}"},
                    })
                continue
            try:
                result = handler(self, message.get("params") or {})
            except Exception as exc:  # el editor no debe morir con el servidor
                log(f"error en {method}: {exc}")
                if "id" in message:
                    write_message(stdout, {
                        "jsonrpc": "2.0", "id": message["id"],
                        "error": {"code": -32603, "message": str(exc)},
                    })
                continue
            if "id" in message:  # es peticion, no notificacion: hay que responder
                write_message(stdout, {"jsonrpc": "2.0", "id": message["id"], "result": result})
        return 0


def main() -> int:
    log(f"{SERVER_NAME} {SERVER_VERSION} escuchando por stdio "
        f"(modelo FIM: {fim.MODEL}, disparo: {COMPLETION_TRIGGER})")
    return CodeCopilotServer().serve(sys.stdin.buffer, sys.stdout.buffer)


if __name__ == "__main__":
    sys.exit(main())
