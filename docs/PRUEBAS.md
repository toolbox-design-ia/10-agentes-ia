# Pruebas del repositorio

Todo el codigo de este repositorio se ha ejecutado antes de publicarlo. Estas
son las pruebas y lo que cubre cada una. Se lanzan con el interprete del venv,
desde la raiz del repositorio, con Ollama corriendo.

```bash
.venv/bin/python tests/test_base_agent.py      # 12  patron del capitulo 3
.venv/bin/python tests/test_copilot_lsp.py     # 12  protocolo LSP + FIM real
.venv/bin/python tests/test_copilot_runner.py  #  5  reparacion con pytest real
.venv/bin/python tests/test_minutes.py         # 14  dos pasadas + Pydantic
.venv/bin/python tests/test_vad.py             # 19  deteccion de fin de turno
.venv/bin/python tests/test_orchestrator.py    # 11  catalogo, despacho y trazas
```

## Que se probo de verdad

| Prueba | Modelo usado | Con modelo real? |
| --- | --- | --- |
| `test_base_agent` | `qwen2.5-coder:7b` | Si: el modelo elige la herramienta y redacta con su resultado |
| `test_copilot_lsp` | `qwen2.5-coder:1.5b` | Si: completado FIM real por el protocolo |
| `test_copilot_runner` | `qwen2.5-coder:1.5b` | Si: repara un bug real (`<=` por `<`) y pytest pasa |
| `test_minutes` | `qwen2.5-coder:7b` | Si: extrae decisiones y tareas de una transcripcion |
| `test_vad` | — | No hace falta: audio sintetico |
| `test_orchestrator` | `qwen3:14b` | Si: tool calling nativo, invoca al bibliotecario |

## Que NO se ha podido probar, y por que

El servidor de pruebas es headless (sin tarjeta de sonido, sin PortAudio
instalable por falta de permisos de administrador) y tiene una GPU AMD via
ROCm, no una NVIDIA. Queda por probar en una maquina de escritorio:

1. **Captura real desde microfono** (`vad.record_turn`). La maquina de estados
   que decide el fin de turno SI esta probada, con audio sintetico de silencio,
   ruido de ventilador y voz; lo que no se ha ejercitado es la lectura del
   `RawInputStream` de sounddevice, porque falta PortAudio.
2. **Sintesis con Piper** (`speak`). No hay binario de Piper ni tarjeta de
   sonido. La funcion esta escrita para devolver `False` sin lanzar excepcion
   cuando Piper falta, y ese camino si esta probado.
3. **Transcripcion con Whisper** sobre audio real. `openai-whisper` necesita
   `ffmpeg`, que no esta instalado en el servidor de pruebas.
4. **El agente de correo** (`03_mail_clerk`) contra un servidor IMAP real: hace
   falta una cuenta con contrasena de aplicacion. La clase, el catalogo de
   herramientas y el despacho si estan probados.
5. **El lector de facturas** con un modelo de vision: `llama3.2-vision:11b` no
   cabe en el hardware de pruebas.
6. **Las cifras de latencia del README del capitulo 11** se midieron en ese
   servidor AMD/ROCm. En una GPU NVIDIA de escritorio seran menores; la tabla
   dice donde se midio precisamente para que nadie la lea como universal.
