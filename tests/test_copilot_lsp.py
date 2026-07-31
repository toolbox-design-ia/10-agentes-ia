"""Prueba de extremo a extremo del servidor LSP: cliente real por stdio."""
import json, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = Path(sys.executable)

class Client:
    def __init__(self):
        self.p = subprocess.Popen(
            [str(PY), str(REPO/"agents/08_code_copilot/lsp_server.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=str(REPO))
        self._id = 0
    def send(self, method, params=None, notify=False):
        msg = {"jsonrpc":"2.0","method":method}
        if params is not None: msg["params"] = params
        if not notify:
            self._id += 1; msg["id"] = self._id
        body = json.dumps(msg).encode()
        self.p.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode()+body)
        self.p.stdin.flush()
        return None if notify else self.recv()
    def recv(self):
        headers = {}
        while True:
            line = self.p.stdout.readline()
            if not line: raise RuntimeError("servidor cerro la tuberia")
            line = line.decode().strip()
            if not line: break
            k,v = line.split(":",1); headers[k.strip().lower()] = v.strip()
        return json.loads(self.p.stdout.read(int(headers["content-length"])).decode())

FIXTURE = '''def suma_pares(numeros):
    """Devuelve la suma de los numeros pares de la lista."""
    total = 0
    for n in numeros:
    return total


def media(numeros):
    return sum(numeros) / len(numeros)
'''

ok = lambda c,m: print(("  PASA  " if c else "  FALLA ") + m) or c

def main():
    results = []
    c = Client()
    print("== 1. initialize ==")
    r = c.send("initialize", {"processId": None, "rootUri": None,
                              "clientInfo": {"name":"prueba-e2e"}, "capabilities":{}})
    caps = r["result"]["capabilities"]
    results.append(ok("completionProvider" in caps, "anuncia completionProvider"))
    results.append(ok("codeCopilot.runTests" in caps["executeCommandProvider"]["commands"],
                      "anuncia el comando codeCopilot.runTests"))
    results.append(ok(caps["textDocumentSync"] == 1, "textDocumentSync = full"))
    print("   serverInfo:", r["result"]["serverInfo"])
    c.send("initialized", {}, notify=True)

    print("== 2. didOpen + completion (FIM real contra Ollama) ==")
    uri = "file:///tmp/fixture_copiloto.py"
    c.send("textDocument/didOpen",
           {"textDocument":{"uri":uri,"languageId":"python","version":1,"text":FIXTURE}},
           notify=True)
    # cursor justo despues de "for n in numeros:\n" -> linea 4, col 0
    t0 = time.monotonic()
    r = c.send("textDocument/completion",
               {"textDocument":{"uri":uri},"position":{"line":4,"character":0},
                "context":{"triggerKind":1}})
    dt = time.monotonic()-t0
    items = r["result"]["items"]
    results.append(ok(len(items) == 1, f"devuelve 1 sugerencia en {dt:.2f}s"))
    if items:
        texto = items[0]["insertText"]
        print("   detail:", items[0]["detail"])
        print("   insertText:", repr(texto[:120]))
        results.append(ok("total" in texto and "%" in texto or "if" in texto,
                          "la sugerencia rellena el hueco con codigo plausible"))
        results.append(ok("textEdit" in items[0], "incluye textEdit con rango"))

    print("== 3. disparo implicito se ignora (triggerKind=2) ==")
    r = c.send("textDocument/completion",
               {"textDocument":{"uri":uri},"position":{"line":4,"character":0},
                "context":{"triggerKind":2}})
    results.append(ok(r["result"]["items"] == [], "no sugiere al teclear (modo explicit)"))

    print("== 4. didChange se refleja en el documento ==")
    c.send("textDocument/didChange",
           {"textDocument":{"uri":uri,"version":2},
            "contentChanges":[{"text":"def f():\n    pass\n"}]}, notify=True)
    r = c.send("textDocument/completion",
               {"textDocument":{"uri":uri},"position":{"line":1,"character":0},
                "context":{"triggerKind":1}})
    results.append(ok("result" in r, "responde tras didChange sin romperse"))

    print("== 5. metodo desconocido -> error JSON-RPC, servidor vivo ==")
    r = c.send("textDocument/inventado", {})
    results.append(ok(r.get("error",{}).get("code") == -32601, "error -32601 y no muere"))
    r = c.send("textDocument/completion",
               {"textDocument":{"uri":uri},"position":{"line":0,"character":0},
                "context":{"triggerKind":2}})
    results.append(ok("result" in r, "sigue respondiendo despues del error"))

    print("== 6. shutdown / exit ==")
    r = c.send("shutdown")
    results.append(ok("result" in r, "responde a shutdown"))
    c.send("exit", notify=True)
    time.sleep(1.0)
    c.p.wait(timeout=10)
    results.append(ok(c.p.returncode == 0, f"sale con codigo {c.p.returncode}"))
    err = c.p.stderr.read().decode()
    if err.strip(): print("   stderr:", err.strip()[:300])

    print(f"\n== RESULTADO: {sum(results)}/{len(results)} comprobaciones pasan ==")
    return 0 if all(results) else 1

if __name__ == "__main__":
    sys.exit(main())
