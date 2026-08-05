#!/usr/bin/env bash
#
# Scrive un messaggio sulla matrice LED. È il comando che Kalico invoca da
# `[gcode_shell_command LED_MSG]` (vedi docs/06-matrice-led.md):
#
#   command: /home/pi/G2-Service/matrix/run_display.sh
#
# Esiste perché `gcode_shell_command` vuole un singolo eseguibile a cui accoda i `PARAMS`:
# non ci si può infilare la riga `venv/bin/python led_matrix_display.py`.
#
# Il messaggio arriva **spezzato in più argomenti** — Kalico passa i PARAMS separati dagli
# spazi — quindi si ricompone con "$*", altrimenti `LED_MESSAGE MSG="STAMPA IN CORSO"`
# mostrerebbe solo "STAMPA".

set -euo pipefail

MATRIX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$MATRIX_DIR/../venv/bin/python"
DISPLAY_PY="$MATRIX_DIR/led_matrix_display.py"

MSG="$*"

if [ -z "$MSG" ]; then
	echo "run_display.sh: nessun messaggio da mostrare" >&2
	exit 1
fi

if [ ! -x "$PYTHON" ]; then
	echo "run_display.sh: virtualenv assente ($PYTHON). Esegui Scripts/install.sh" >&2
	exit 1
fi

# In background e con gli stream chiusi, per due motivi distinti:
#
#   - il processo Python **resta vivo** dopo aver scritto (luma spegne il display quando il
#     processo termina), mentre il gcode non deve fermarsi ad aspettarlo;
#   - `gcode_shell_command` legge l'output del comando e aspetta la chiusura della pipe: se il
#     figlio la tenesse aperta, la macro resterebbe bloccata fino al `timeout: 10`.
nohup "$PYTHON" "$DISPLAY_PY" "$MSG" >/dev/null 2>&1 &
