# 10 agentes de IA que puedes crear hoy — Código del libro

Repositorio companion del libro **«10 agentes de IA que puedes crear hoy»**
(Henry Ramírez Reyes, serie INTELIGENCIA ARTIFICIAL, Studio35).

El libro explica y decide; este repositorio ejecuta: aquí está el código
COMPLETO de los diez agentes, la instalación guiada y la guía de errores.

## Puesta en marcha (Anexo A del libro)

```
git clone https://github.com/studio35post/10-agentes-ia.git
cd 10-agentes-ia

# macOS / Linux
./setup.sh            # crea el venv, instala dependencias y verifica Ollama

# Windows (PowerShell)
.\setup.ps1

cp .env.example .env  # rellena tus credenciales (el libro lo guía campo a campo)
python run.py         # menú: elige qué agente lanzar
```

Requisitos: Python 3.11+ y [Ollama](https://ollama.com) instalado.
Hardware por agente: ver la tabla de VRAM del capítulo 2.

## Estructura

- `core/` — el patrón de agente reutilizable (capítulo 3)
- `hello_agent.py` — la prueba de vida del capítulo 3, ejecutable tal cual
- `agents/NN_*/` — un directorio por agente (capítulos 4-13), cada uno con su
  `README` y su código completo
- `prompts/` — plantillas de prompt en texto plano, separadas del código
- `data/`, `traces/` — datos de trabajo y trazas (no se versionan)
- `docs/troubleshooting.md` — la guía de solución de problemas (Anexo B)

## Correspondencia capítulo → código

| Capítulo | Carpeta |
| --- | --- |
| 3. El patrón de agente | `core/` + `hello_agent.py` |
| 4. Tu segundo cerebro privado | `agents/01_second_brain/` |
| 5. El bibliotecario | `agents/02_librarian/` |
| 6. El secretario de correo | `agents/03_mail_clerk/` |
| 7. El acta perfecta | `agents/04_meeting_notes/` |
| 8. El lector de facturas | `agents/05_invoice_reader/` |
| 9. El vigía de la web | `agents/06_web_watcher/` |
| 10. El documentalista | `agents/07_researcher/` |
| 11. El copiloto de código | `agents/08_code_copilot/` |
| 12. El asistente de voz | `agents/09_voice_assistant/` |
| 13. El equipo | `agents/10_orchestrator/` |

Los fragmentos impresos en el libro corresponden a estos archivos; donde el
capítulo imprime una función, aquí está con el mismo nombre. Este
repositorio es también la fe de erratas viva del libro: si encuentras un
error, abre un issue.

## Licencia

MIT para el código. El texto del libro tiene todos los derechos reservados.
