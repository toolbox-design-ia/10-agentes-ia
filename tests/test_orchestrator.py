import importlib, json, os, sys, time
from pathlib import Path
R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
os.environ["ORCHESTRATOR_MODEL"] = os.environ.get("ORCH_MODEL", "qwen3:14b")
o = importlib.import_module("agents.10_orchestrator.agent")
res=[]; ok=lambda c,t:(print(("  PASA  " if c else "  FALLA ")+t), res.append(c))[1]

print("== 1. catalogo bien formado para la API de Ollama ==")
ok(len(o.TOOLS)==9, f"nueve herramientas ({len(o.TOOLS)})")
ok(all(h["type"]=="function" and "name" in h["function"] and
       "parameters" in h["function"] for h in o.TOOLS), "todas con envoltorio type/function")
ok(all("NO " in h["function"]["description"] for h in o.TOOLS),
   "todas declaran lo que NO hacen (limites en el contrato)")

print("\n== 2. despacho: herramienta desconocida ==")
try: o.ejecutar_herramienta("inventada", {}); ok(False,"deberia lanzar")
except ValueError as e: ok("desconocida" in str(e), f"error claro: {e}")

print("\n== 3. despacho REAL a un especialista (bibliotecario) ==")
D = Path("/tmp/orq_prueba"); D.mkdir(exist_ok=True)
for n in ["a.jpg","b.mp3","c.csv"]: (D/n).write_text("x")
r = o.ejecutar_herramienta("bibliotecario", {"carpeta": str(D)})
print("   ", str(r)[:220])
ok("Imagenes" in r["plan"] and "Audio" in r["plan"], "el bibliotecario responde de verdad")

print("\n== 4. trazas: se escribe el JSONL y el directorio se crea solo ==")
if o.TRACES_FILE.exists(): o.TRACES_FILE.unlink()
o.registrar_traza("bibliotecario", {"carpeta": str(D)}, r, 0.42)
ok(o.TRACES_FILE.exists(), f"crea {o.TRACES_FILE}")
linea = json.loads(o.TRACES_FILE.read_text().strip().splitlines()[-1])
print("   ", linea)
ok(linea["agente"]=="bibliotecario" and linea["duracion_s"]==0.42, "la traza registra agente y duracion")

print("\n== 5. BUCLE COMPLETO: modelo real elige y ejecuta ==")
t0=time.monotonic()
salida = o.orquestar(f"Dime como habria que ordenar la carpeta {D}. Usa una herramienta.")
dt=time.monotonic()-t0
print(f"   respuesta ({dt:.1f}s):\n   " + salida.replace("\n","\n   ")[:600])
ok(len(salida.strip())>0, "el orquestador devuelve respuesta")
trazas = o.TRACES_FILE.read_text().strip().splitlines()
usadas = [json.loads(l)["agente"] for l in trazas[1:]]
print("   herramientas invocadas en este turno:", usadas)
ok(len(usadas)>=1, f"invoco al menos un especialista: {usadas}")
ok(any(x in salida for x in ("a.jpg","b.mp3","c.csv","Imagenes","Audio")),
   "la respuesta contiene datos que solo salen de ejecutar la herramienta")

print("\n== 6. liberar_modelo (keep_alive=0) contra Ollama real ==")
try:
    o.liberar_modelo("qwen2.5-coder:1.5b"); ok(True,"descarga el modelo sin error")
except Exception as e: ok(False, f"fallo: {e}")

print(f"\n== RESULTADO: {sum(res)}/{len(res)} ==")
sys.exit(0 if all(res) else 1)
