#!/usr/bin/env bash
#
# Scrive un messaggio sulla matrice LED. È il comando che Kalico invoca da
# `[gcode_shell_command LED_MSG]` (vedi docs/06-matrice-led.md):
#
#   command: /bin/bash /home/pi/G2-Service/matrix/run_display.sh
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

# Opzioni della singola macchina, per esempio la matrice pilotata da un ESP32 via seriale:
#   MATRIX_ARGS="--uart /dev/serial0"
# Il file sta fuori dal repository così un aggiornamento non lo tocca; se manca si usa lo SPI.
MATRIX_ARGS=""
MATRIX_ENV="/etc/g2/matrix.env"
if [ -r "$MATRIX_ENV" ]; then
	# shellcheck source=/dev/null
	. "$MATRIX_ENV"
fi

if [ -z "$MSG" ]; then
	echo "run_display.sh: nessun messaggio da mostrare" >&2
	exit 1
fi

if [ ! -x "$PYTHON" ]; then
	echo "run_display.sh: virtualenv assente ($PYTHON). Esegui Scripts/install.sh" >&2
	exit 1
fi

# Termina **qui**, prima di lanciare il nuovo, ogni processo della matrice ancora vivo.
# Il controllo nel Python non basta: parte solo dopo circa un secondo di import, e con due
# LED_MESSAGE ravvicinati i due nuovi processi leggono lo stesso PID vecchio e sopravvivono
# entrambi. Con il backend seriale ognuno rimanda il suo frame ogni 5 s, e la matrice
# lampeggia fra i due messaggi. Qui invece non c'è concorrenza: Kalico esegue i comandi shell
# uno alla volta. Il pattern contiene `.py`, quindi non prende questo script.
pkill -f "matrix/led_matrix_display\.py" || true
for _ in 1 2 3 4 5 6 7 8 9 10; do
	pgrep -f "matrix/led_matrix_display\.py" >/dev/null || break
	sleep 0.1
done
pkill -KILL -f "matrix/led_matrix_display\.py" || true

# In background e con gli stream chiusi, per due motivi distinti:
#
#   - il processo Python **resta vivo** dopo aver scritto (luma spegne il display quando il
#     processo termina), mentre il gcode non deve fermarsi ad aspettarlo;
#   - `gcode_shell_command` legge l'output del comando e aspetta la chiusura della pipe: se il
#     figlio la tenesse aperta, la macro resterebbe bloccata fino al `timeout: 10`.
# shellcheck disable=SC2086 # MATRIX_ARGS va diviso nelle singole opzioni
nohup "$PYTHON" "$DISPLAY_PY" $MATRIX_ARGS "$MSG" >/dev/null 2>&1 &
