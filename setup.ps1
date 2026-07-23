# Instalacion guiada en Windows (Anexo A del libro): venv + dependencias.
# Si PowerShell bloquea el script:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$ErrorActionPreference = "Stop"

$version = python -c "import sys; print(sys.version_info >= (3, 11))" 2>$null
if ($version -ne "True") {
    Write-Host "ERROR: se necesita Python 3.11 o superior."
    Write-Host "El capitulo 2 del libro explica como instalar la version correcta."
    exit 1
}

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt

if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "Ollama detectado: $(ollama --version)"
} else {
    Write-Host "AVISO: Ollama no esta instalado. Descargalo de https://ollama.com"
    Write-Host "       (capitulo 2 del libro, paso a paso por sistema operativo)."
}

Write-Host "Listo. Activa el entorno con: .\.venv\Scripts\Activate.ps1"
Write-Host "Y arranca el menu con:       python run.py"
