# El copiloto de codigo — capitulo 11

Tres piezas, de menos a mas ambiciosa:

| Pieza | Archivo | Que hace |
| --- | --- | --- |
| CLI | `agent.py` | Recibe archivo + instruccion, propone la version nueva y la muestra como diff. Solo escribe con `--apply`, dejando `.bak`. |
| Servidor LSP | `lsp_server.py` | Habla Language Server Protocol por stdio: cualquier editor cliente LSP obtiene completado FIM sin plugin propio. |
| Ejecutor de tests | `test_runner.py` | Aplica una propuesta en una copia de trabajo, lanza `pytest`, y devuelve el fallo al modelo para que corrija, hasta 3 intentos. |
| FIM | `fim.py` | Completado fill-in-the-middle: prefijo + sufijo, via el parametro `suffix` de Ollama. |

Variables del `.env`: `OLLAMA_MODEL`, `COPILOT_FIM_MODEL`, `COPILOT_REPAIR_MODEL`,
`COPILOT_COMPLETION_TRIGGER`, `COPILOT_PREFIX_LINES`, `COPILOT_SUFFIX_LINES`.

## Uso

```bash
# 1. CLI
python agents/08_code_copilot/agent.py script.py "anade manejo de errores" [--apply]

# 2. Ejecutor de tests
python agents/08_code_copilot/test_runner.py buscar.py test_buscar.py "corrige el indice"

# 3. Servidor LSP (lo lanza el editor, no tu)
python agents/08_code_copilot/lsp_server.py
```

Configuracion de ejemplo para Neovim (`vim.lsp.start`) o cualquier cliente LSP:
el comando es el interprete del venv seguido de la ruta de `lsp_server.py`, y
el transporte es stdio. El servidor anuncia `completionProvider` y el comando
`codeCopilot.runTests`.

## El modelo FIM NO puede ser un generalista

`llama3.1`, `mistral` y compania no traen plantilla de fill-in-the-middle:
Ollama responde `400 does not support insert`. `fim.py` lo detecta y lanza
`ModelDoesNotSupportFIM` con el mensaje de que uses `qwen2.5-coder`,
`deepseek-coder` o `codellama:7b/13b`.

## Latencia medida (por que el disparo es explicito)

Medido en el servidor de pruebas (AMD ROCm en contenedor, sin GPU NVIDIA),
mediana de 5 ejecuciones, primera llamada excluida:

| Modelo | Completado corto | Firma de funcion | Cuerpo de metodo |
| --- | --- | --- | --- |
| `qwen2.5-coder:1.5b` | 0,35 s | 0,39 s | 1,60 s |
| `qwen2.5-coder:7b` | 1,08 s | 1,32 s | 5,99 s |

El autocompletado que aparece solo, mientras escribes, vive en un presupuesto
de decenas o pocos cientos de milisegundos. Ninguna de esas cifras entra ahi.
Por eso `COPILOT_COMPLETION_TRIGGER=explicit` es el valor por defecto: el
copiloto sugiere cuando se lo pides, no a cada tecla. Con `always` y el modelo
de 1,5B la experiencia es tolerable para completados cortos; con el de 7B, no.

Quien tenga una GPU mas rapida que este banco de pruebas vera cifras menores y
puede subir a `always`: la estrategia es configuracion, no codigo.

## Pruebas

```bash
python tests/test_copilot_lsp.py     # 12 comprobaciones del protocolo + FIM real
python tests/test_copilot_runner.py  # 5 grupos: repara un bug real con pytest
```
