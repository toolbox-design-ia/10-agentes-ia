# Guía de solución de problemas (Anexo B del libro)

Formato: síntoma → causa → solución. Se completa con el Anexo B.

## ModuleNotFoundError: No module named '...'
El entorno virtual no está activado o las dependencias no se instalaron.
`source .venv/bin/activate` y después `pip install -r requirements.txt`.

## CUDA out of memory / el modelo no arranca
El modelo elegido no cabe en tu VRAM. Consulta la tabla del capítulo 2 y
baja un escalón (p. ej. de 30B a 8B, o una cuantización menor).

(…el Anexo B del libro desarrolla la lista completa…)
