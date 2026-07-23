#!/usr/bin/env bash
# Instalacion guiada (Anexo A del libro): venv + dependencias + verificacion.
set -e
PY=python3
if ! $PY -c 'import sys; assert sys.version_info >= (3, 11)' 2>/dev/null; then
  echo "ERROR: se necesita Python 3.11 o superior. Instalado: $($PY -V 2>&1)"
  echo "El capitulo 2 del libro explica como instalar la version correcta."
  exit 1
fi
$PY -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt
if ! command -v ollama >/dev/null; then
  echo "AVISO: Ollama no esta instalado. Descargalo de https://ollama.com"
  echo "       (capitulo 2 del libro, paso a paso por sistema operativo)."
else
  echo "Ollama detectado: $(ollama --version 2>/dev/null | head -1)"
fi
echo "Listo. Activa el entorno con: source .venv/bin/activate"
echo "Y arranca el menu con:        python run.py"
