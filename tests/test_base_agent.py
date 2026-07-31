"""El bucle del capitulo 3, de verdad: modelo real eligiendo herramienta real."""
import importlib, os, sys, time, json
from pathlib import Path
R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
os.environ["OLLAMA_MODEL"] = os.environ.get("TEST_MODEL", "qwen2.5-coder:7b")

from core.base_agent import BaseAgent
from core.tools import validate_call, build_tools_prompt, ToolCallError

res = []
def ok(c, m):
    print(("  PASA  " if c else "  FALLA ") + m); res.append(c); return c

print("== 1. el prompt de herramientas se construye a partir del catalogo ==")
lib = importlib.import_module("agents.02_librarian.agent")
A = lib.LibrarianAgent
a = A(); a.model = os.environ["OLLAMA_MODEL"]
p = build_tools_prompt(a.tools)
ok("plan_moves(folder)" in p and "classify_file(path)" in p, "prompt lista las 2 herramientas con sus parametros")
print("   " + p.replace("\n", "\n   "))

print("\n== 2. validate_call acepta lo bueno y rechaza lo malo ==")
ok(validate_call('{"tool":"plan_moves","params":{"folder":"/tmp/biblio"}}', a.tools)["tool"] == "plan_moves",
   "acepta una llamada valida")
for mal, motivo in [('no soy json', "JSON invalido"),
                    ('{"params":{}}', "falta 'tool'"),
                    ('{"tool":"inventada","params":{}}', "herramienta inexistente")]:
    try:
        validate_call(mal, a.tools); ok(False, f"deberia rechazar: {motivo}")
    except ToolCallError as e:
        ok(True, f"rechaza {motivo}: {e}")

print("\n== 3. BUCLE COMPLETO con modelo real: pregunta -> herramienta -> respuesta ==")
D = Path("/tmp/biblio_prueba"); D.mkdir(exist_ok=True)
for n in ["informe.pdf", "foto.jpg", "cancion.mp3", "datos.csv", "video.mp4"]:
    (D / n).write_text("x")
t0 = time.monotonic()
salida = a.run(f"Organiza la carpeta {D}. Usa la herramienta.")
dt = time.monotonic() - t0
print("   respuesta del agente (%.1fs):" % dt)
print("   " + salida.replace("\n", "\n   ")[:700])
ok(len(salida.strip()) > 0, "el bucle termina y devuelve texto")
ok(any(x in salida for x in ("foto.jpg", "Imagenes", "cancion.mp3", "Audio", "video.mp4")),
   "la respuesta contiene datos que SOLO salen de ejecutar la herramienta")

print("\n== 4. herramienta directa: la funcion real hace el trabajo ==")
directo = lib.tool_plan_moves(str(D))
print("   " + directo.replace("\n", "\n   ")[:300])
ok("Imagenes" in directo and "Audio" in directo, "plan_moves clasifica por extension")

print("\n== 5. sin herramienta: responde en texto normal sin romperse ==")
salida2 = a.run("Hola, en una frase: para que sirves?")
print("   " + salida2.replace("\n", "\n   ")[:250])
ok(len(salida2.strip()) > 0 and "No se pudo obtener" not in salida2,
   "responde directo cuando no hace falta herramienta")

print("\n== 6. reintento: el modelo se corrige tras un error de contrato ==")
class Terco(BaseAgent):
    system_prompt = "test"
    tools = {"eco": {"description": "devuelve el texto", "params": {"texto": "que decir"},
                     "func": lambda texto="": f"ECO:{texto}"}}
    _n = 0
    def _chat(self, messages):
        Terco._n += 1
        # 1a: JSON roto. 2a: herramienta inventada. 3a: correcta. 4a: texto final.
        return ['{"tool": "eco", params: roto}',
                '{"tool":"noexiste","params":{}}',
                '{"tool":"eco","params":{"texto":"hola"}}',
                'Listo: el eco dice hola.'][min(Terco._n - 1, 3)]
r = Terco().run("da igual", max_retries=2)
ok("hola" in r and Terco._n == 4, f"se recupera de 2 errores, ejecuta y redacta (n={Terco._n}, r={r!r})")

print("\n== 6b. herramienta que revienta: el error vuelve al modelo, no al usuario ==")
class Explota(BaseAgent):
    system_prompt = "t"
    def _boom(**kw): raise RuntimeError("disco lleno")
    tools = {"x": {"description": "d", "params": {}, "func": _boom}}
    _n = 0
    def _chat(self, messages):
        Explota._n += 1
        return '{"tool":"x","params":{}}' if Explota._n == 1 else "No pude: el disco esta lleno."
r3 = Explota().run("hazlo")
ok("disco" in r3 and "Traceback" not in r3, f"la excepcion se convierte en observacion: {r3!r}")

print("\n== 7. agota reintentos sin inventar resultado ==")
class Siempre(Terco):
    _n = 0
    def _chat(self, messages): return "{roto, no es json"
r2 = Siempre().run("x", max_retries=1)
ok("No se pudo obtener" in r2, f"falla explicitamente: {r2!r}")

print(f"\n== RESULTADO: {sum(res)}/{len(res)} ==")
sys.exit(0 if all(res) else 1)
