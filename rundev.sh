#!/usr/bin/env bash
# Sviluppo locale, anche su macOS: crea (se manca) un venv nella cartella del repo, installa le
# dipendenze e avvia uvicorn con reload. Nessun privilegio richiesto: la modalità mock si attiva
# da sola fuori da Linux (vedi src/settings.py e docs/05-deploy-e-sviluppo.md).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

VENV_DIR="$REPO_ROOT/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creo il venv in $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

exec uvicorn src.main:app --reload --host "${G2_SERVICE_HOST:-0.0.0.0}" --port "${G2_SERVICE_PORT:-8000}"
