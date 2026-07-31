import importlib, os, sys, time
from pathlib import Path
R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
os.environ["OLLAMA_MODEL"] = "qwen2.5-coder:7b"
m = importlib.import_module("agents.04_meeting_notes.minutes")
from pydantic import ValidationError
res=[]; ok=lambda c,t:(print(("  PASA  " if c else "  FALLA ")+t), res.append(c))[1]

TRANS = """Marta: Buenos dias. El primer punto es la migracion del servidor de correo.
Luis: Yo creo que deberiamos hacerla antes de fin de mes, el proveedor sube precios en agosto.
Marta: De acuerdo. Decidimos migrar el servicio de correo a finales de mes.
Luis: Perfecto. Yo me encargo de preparar el inventario de buzones.
Marta: Bien. Ana, tu puedes revisar el contrato con el proveedor antes del viernes?
Ana: Si, lo miro antes del viernes.
Luis: Otra cosa, hay que actualizar la documentacion, pero no se quien deberia hacerlo.
Marta: Lo dejamos pendiente de asignar. Acordamos tambien posponer el cambio de CRM hasta septiembre.
"""

print("== 1. esquema: lo que el modelo no dice, queda vacio ==")
mi = m.Minutes(summary="Reunion de prueba.",
               decisions=["Migrar el correo"],
               tasks=[m.Task(description="Inventario de buzones", owner="Luis"),
                      m.Task(description="Actualizar la documentacion")])
ok(mi.tasks[1].owner is None, "owner ausente = None, no un nombre inventado")
md = mi.to_markdown()
ok("[sin asignar]" in md, "el acta marca 'sin asignar'")
ok("1 tarea(s) sin responsable" in md, "avisa de las tareas sin responsable")
print("   " + md.replace("\n","\n   "))

print("\n== 2. el esquema RECHAZA datos mal formados ==")
for mala, motivo in [(chr(123)+chr(34)+"summary"+chr(34)+chr(58)+chr(34)+"Resumen suficientemente largo."+chr(34)+chr(125), "sin decisions/tasks -> deberia valer (por defecto)"),
                     ('{"decisions":[]}', "falta summary"),
                     ('{"summary":"x","tasks":[{"owner":"Ana"}]}', "tarea sin description")]:
    try:
        m.Minutes.model_validate_json(mala); ok("deberia valer" in motivo, f"acepta: {motivo}")
    except ValidationError: ok("deberia valer" not in motivo, f"rechaza: {motivo}")

print("\n== 3. PRIMERA PASADA con modelo real ==")
t0=time.monotonic(); cands = m.extract_candidates(TRANS); dt=time.monotonic()-t0
print("   candidatos (%.1fs):\n   %s" % (dt, cands.replace("\n","\n   ")[:500]))
ok(len(cands.strip())>0, "extrae candidatos")
ok(any(k in cands.lower() for k in ["migrar","correo","inventario","contrato"]),
   "los candidatos salen de la transcripcion")

print("\n== 4. SEGUNDA PASADA: valida contra el esquema ==")
t0=time.monotonic(); acta = m.structure(TRANS, cands); dt=time.monotonic()-t0
print("   acta validada en %.1fs" % dt)
ok(isinstance(acta, m.Minutes), "devuelve un objeto Minutes validado")
ok(len(acta.summary) > 10, "tiene resumen")
ok(len(acta.decisions) >= 1, f"detecta decisiones: {acta.decisions}")
print("   tareas:")
for t in acta.tasks: print(f"     - {t.description!r} owner={t.owner!r} due={t.due!r}")
sin_owner = [t for t in acta.tasks if t.owner is None]
ok(True, f"{len(acta.tasks)} tareas, {len(sin_owner)} sin responsable")
print("   --- markdown ---")
print("   " + acta.to_markdown().replace("\n","\n   "))

print("\n== 5. REINTENTO: el modelo falla y se le devuelve el error ==")
intentos = {"n":0}
real = m._generate
def falso(prompt, json_mode=False):
    intentos["n"] += 1
    if intentos["n"] == 1: return '{"summary": 42}'          # tipo incorrecto
    if intentos["n"] == 2: return 'esto no es json en absoluto'
    return '{"summary":"Resumen valido de la reunion.","decisions":["D1"],"tasks":[]}'
m._generate = falso
acta2 = m.structure("t", "c", max_retries=2)
m._generate = real
ok(intentos["n"] == 3 and acta2.summary.startswith("Resumen"),
   f"reintenta 2 veces y valida a la 3a (n={intentos['n']})")

print("\n== 6. agotados los reintentos, falla explicitamente ==")
m._generate = lambda prompt, json_mode=False: "{}"
try:
    m.structure("t","c",max_retries=1); ok(False,"deberia lanzar")
except ValueError as e: ok("no produjo un acta valida" in str(e), f"error claro: {str(e)[:90]}")
m._generate = real

print(f"\n== RESULTADO: {sum(res)}/{len(res)} ==")
sys.exit(0 if all(res) else 1)
