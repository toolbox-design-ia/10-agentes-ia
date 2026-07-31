"""Prueba del ejecutor de tests: archivo roto de verdad + pytest real."""
import json, subprocess, sys, time
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import importlib
tr = importlib.import_module("agents.08_code_copilot.test_runner")

TMP = Path("/tmp/copiloto_fixture"); TMP.mkdir(exist_ok=True)

# Bug real y sutil: usa <= en vez de <, asi que se sale del rango
ROTO = '''def buscar(lista, objetivo):
    """Devuelve el indice de objetivo en lista, o -1 si no esta."""
    i = 0
    while i <= len(lista):
        if lista[i] == objetivo:
            return i
        i += 1
    return -1
'''

TESTS = '''from buscar import buscar

def test_encuentra():
    assert buscar([1, 2, 3], 2) == 1

def test_no_esta():
    assert buscar([1, 2, 3], 9) == -1

def test_lista_vacia():
    assert buscar([], 1) == -1
'''

(TMP/"buscar.py").write_text(ROTO); (TMP/"test_buscar.py").write_text(TESTS)

print("== 0. el archivo falla de verdad antes de empezar ==")
ok0, out0 = tr.run_pytest(TMP, "test_buscar.py")
print("   pytest verde?", ok0, "|", tr.summarize(out0))
assert not ok0, "el fixture deberia fallar"
assert "IndexError" in out0, "deberia ser un IndexError"
print("   PASA  el fixture falla con IndexError, como se esperaba")

print("\n== 1. bucle de reparacion (modelo real, hasta 3 intentos) ==")
t0 = time.monotonic()
rep = tr.repair_until_green(TMP/"buscar.py", TMP/"test_buscar.py",
                            "corrige el error de indice", max_attempts=3)
dt = time.monotonic()-t0
for a in rep.attempts:
    print(f"   intento {a.number}: {'PASA' if a.passed else 'FALLA'} — {a.summary}")
print(f"   convergio: {rep.passed}  en {dt:.1f}s")
if rep.passed:
    print("   --- codigo final ---")
    print("   " + rep.final_source.replace("\n","\n   ")[:400])

print("\n== 2. el archivo ORIGINAL no se ha tocado ==")
sigue_roto = (TMP/"buscar.py").read_text() == ROTO
print("   PASA " if sigue_roto else "   FALLA ", "el original sigue intacto en disco")

print("\n== 3. el informe serializa a JSON (lo devuelve el LSP) ==")
d = rep.as_dict(); js = json.dumps(d)
print("   PASA  as_dict() -> JSON de", len(js), "bytes, claves:", sorted(d))

print("\n== 4. tope de intentos con un caso imposible ==")
(TMP/"imposible.py").write_text("def f():\n    return 1\n")
(TMP/"test_imposible.py").write_text("from imposible import f\ndef test_x():\n    assert f() == 2 and f() == 3\n")
rep2 = tr.repair_until_green(TMP/"imposible.py", TMP/"test_imposible.py", "arregla", max_attempts=2)
print(f"   intentos usados: {len(rep2.attempts)} | passed={rep2.passed}")
print("   PASA " if not rep2.passed and len(rep2.attempts) <= 2 else "   FALLA ",
      "se detiene sin colgarse y reporta el fallo")

print("\n== 5. proteccion de timeout (bucle infinito) ==")
(TMP/"colgado.py").write_text("def f():\n    while True:\n        pass\n")
(TMP/"test_colgado.py").write_text("from colgado import f\ndef test_x():\n    f()\n")
import os; os.environ["COPILOT_PYTEST_TIMEOUT"]="5"
importlib.reload(tr)
t0=time.monotonic(); okc, outc = tr.run_pytest(TMP, "test_colgado.py"); dtc=time.monotonic()-t0
print(f"   corto a los {dtc:.1f}s: {outc[:80]}")
print("   PASA " if not okc and dtc < 15 else "   FALLA ", "el timeout funciona")
