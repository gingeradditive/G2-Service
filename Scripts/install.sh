#!/usr/bin/env bash
#
# Installazione e aggiornamento di G2-Service su Raspberry Pi.
#
# Viene invocato in due momenti diversi e deve funzionare in entrambi:
#
#   1. alla creazione dell'immagine, dal modulo `69-G2-Service` di G2-OS, come
#      `sudo -u pi bash ./Scripts/install.sh` — quindi **dentro il chroot di build**, dove
#      systemd non è realmente attivo;
#   2. a ogni aggiornamento, come `install_script` dell'update_manager di Moonraker.
#
# Da qui la regola che governa tutto il file: **è idempotente**. Ogni passo o è già a posto
# e non fa niente, o porta il sistema nello stato voluto; nessuno assume di essere il primo.
#
# Gira come utente normale (`pi`) con sudo passwordless, che è il default di Raspberry Pi OS,
# ma sopravvive anche se qualcuno lo lancia come root.
#
# `DESTDIR` sposta tutti i percorsi di sistema sotto un prefisso, come in `make install`:
# serve a esercitare lo script su una radice finta senza toccare la macchina.

set -euo pipefail

SERVICE_NAME="g2-service"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$REPO_DIR/Scripts"
VENV_DIR="$REPO_DIR/venv"
MATRIX_DIR="$REPO_DIR/matrix"

# Radice dell'installazione, con la convenzione di `make install`: vuota in produzione, un
# prefisso quando si vuole vedere cosa combinerebbe lo script senza lasciarlo toccare il
# sistema vero.
DESTDIR="${DESTDIR:-}"

UNIT_PATH="$DESTDIR/etc/systemd/system/${SERVICE_NAME}.service"
ETC_DIR="$DESTDIR/etc/g2"
NGINX_ROOT="$DESTDIR/etc/nginx"
NGINX_DIR="$NGINX_ROOT/g2-locations.d"
NGINX_CONF="$NGINX_DIR/g2-service.conf"

info() { printf '[g2-service] %s\n' "$*"; }
warn() { printf '[g2-service] ATTENZIONE: %s\n' "$*" >&2; }
fail() {
	printf '[g2-service] ERRORE: %s\n' "$*" >&2
	exit 1
}

# Il venv deve appartenere all'utente che possiede il repository: è come `pi` che Moonraker
# reinstalla le dipendenze a ogni aggiornamento, e un venv di root gli sarebbe inaccessibile
# (docs 02 — Privilegi).
repo_user() { stat -c '%U' "$REPO_DIR"; }

as_root() {
	if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi
}

as_repo_user() {
	if [ "$(id -u)" -eq 0 ] && [ "$REPO_USER" != "root" ]; then
		sudo -u "$REPO_USER" "$@"
	else
		"$@"
	fi
}

# Il controllo canonico per "systemd è davvero il PID 1", quello che usano anche i maintainer
# script di Debian. Nel chroot di build la directory non esiste: `enable` funziona lo stesso
# (è solo un symlink), `start`/`restart` e il reload di nginx no.
systemd_running() { [ -d "$DESTDIR/run/systemd/system" ]; }

# ------------------------------------------------------------------ passi

create_venv() {
	# Si prova prima con la libreria standard: su Raspberry Pi OS `python3 -m venv` non funziona
	# senza il pacchetto `python3-venv`, che il modulo `69-G2-Service` di G2-OS installa fra le
	# sue `DEPS`. Non ci facciamo comunque affidamento, perché lo script gira anche su immagini
	# costruite prima e su checkout fatti a mano: `virtualenv` c'è di sicuro, lo installa il
	# modulo di Kalico ed è quello con cui Moonraker stesso si crea il proprio venv.
	if as_repo_user python3 -m venv "$VENV_DIR" 2>/dev/null; then
		return 0
	fi
	warn "'python3 -m venv' non disponibile (manca python3-venv?), ripiego su virtualenv"
	rm -rf "$VENV_DIR"
	as_repo_user virtualenv -p python3 "$VENV_DIR"
}

ensure_venv() {
	# Un venv rimasto da una versione di Python diversa (dopo un aggiornamento del sistema)
	# esiste ma non esegue più niente: meglio accorgersene qui che al primo avvio.
	if [ -e "$VENV_DIR" ] && ! "$VENV_DIR/bin/python" -c 'pass' 2>/dev/null; then
		warn "virtualenv non funzionante, lo ricreo"
		rm -rf "$VENV_DIR"
	fi
	if [ ! -x "$VENV_DIR/bin/python" ]; then
		info "creo il virtualenv in $VENV_DIR"
		create_venv || fail "creazione del virtualenv fallita"
	fi
	info "installo le dipendenze"
	as_repo_user "$VENV_DIR/bin/pip" install --disable-pip-version-check --quiet \
		-r "$REPO_DIR/requirements.txt"
}

setup_matrix() {
	# La matrice LED (docs 06) non è un servizio: è uno script che Kalico invoca con
	# `gcode_shell_command`. Le sue dipendenze Python le ha già installate ensure_venv, perché
	# stanno in requirements.txt con i marker di piattaforma. Restano due cose di sistema.
	#
	# Niente qui fa fallire l'installazione: la matrice c'è su tutte le G2, ma questo script
	# gira anche su checkout fatti a mano e su macchine che stampanti non sono, e il servizio
	# di rete non deve restare fermo per colpa di un display.
	if [ ! -d "$MATRIX_DIR" ]; then
		warn "cartella matrix/ assente: salto la configurazione della matrice LED"
		return
	fi

	# git conserva il bit di esecuzione, ma un checkout fatto male o un umask strano no, e il
	# sintomo sarebbe un gcode_shell_command che fallisce senza spiegare perché.
	as_repo_user chmod +x "$MATRIX_DIR/run_display.sh" ||
		warn "non sono riuscito a rendere eseguibile matrix/run_display.sh"

	if [ -n "$DESTDIR" ]; then
		info "DESTDIR impostato: non tocco la configurazione SPI del sistema vero"
		return
	fi
	if ! command -v raspi-config >/dev/null 2>&1; then
		warn "raspi-config non trovato: abilita SPI a mano (dtparam=spi=on) o la matrice LED non funzionerà"
		return
	fi
	# `get_spi` risponde 0 quando SPI è già abilitato: evita di riscrivere config.txt a ogni
	# aggiornamento. `do_spi 0` sarebbe comunque idempotente.
	if [ "$(raspi-config nonint get_spi 2>/dev/null)" = "0" ]; then
		info "SPI già abilitato"
		return
	fi
	info "abilito SPI per la matrice LED"
	if as_root raspi-config nonint do_spi 0; then
		warn "SPI appena abilitato: ha effetto dal prossimo riavvio"
	else
		warn "abilitazione di SPI non riuscita: la matrice LED non funzionerà finché non la abiliti"
	fi
}

install_unit() {
	info "installo l'unit systemd in $UNIT_PATH"
	as_root install -d -m 755 "$(dirname "$UNIT_PATH")"
	sed "s|__REPO_DIR__|$REPO_DIR|g" "$SCRIPTS_DIR/${SERVICE_NAME}.service" |
		as_root tee "$UNIT_PATH" >/dev/null

	if systemd_running; then
		as_root systemctl daemon-reload
		as_root systemctl enable "$SERVICE_NAME" ||
			fail "systemctl enable fallito: il servizio non partirebbe al boot"
	else
		# Nel chroot `enable` crea comunque il symlink, ed è ciò che fa partire il servizio
		# al primo boot vero insieme a WantedBy=multi-user.target.
		as_root systemctl enable "$SERVICE_NAME" ||
			warn "systemctl enable non riuscito nel chroot: da verificare al primo boot"
	fi
}

ensure_etc_dir() {
	# Ci vivono il seriale di fabbrica e lo stato delle configurazioni. Resta di root: è root
	# che ci scrive, e non deve essere modificabile da altri.
	as_root install -d -m 755 "$ETC_DIR"
}

install_nginx_location() {
	if ! command -v nginx >/dev/null 2>&1; then
		warn "nginx non è installato: salto la sua configurazione"
		return
	fi

	info "deposito la location nginx in $NGINX_CONF"
	as_root install -d -m 755 "$NGINX_DIR"
	as_root install -m 644 "$SCRIPTS_DIR/${SERVICE_NAME}.nginx.conf" "$NGINX_CONF"

	# -R, non -r: i site in sites-enabled sono symlink a sites-available, e -r non li segue
	# (il site di GingerView include g2-locations.d ma l'avviso usciva lo stesso).
	if ! grep -Rqs 'g2-locations.d' \
		"$NGINX_ROOT/nginx.conf" "$NGINX_ROOT/conf.d" "$NGINX_ROOT/sites-enabled"; then
		warn "nessun site nginx include g2-locations.d/: /service/ non sarà raggiungibile" \
			"dalla porta 80 finché GingerView non aggiunge la riga include (suo TODO NET-5)." \
			"Il servizio resta raggiungibile direttamente sulla porta 8000."
	fi

	if ! systemd_running; then
		warn "systemd non attivo: nginx non viene ricaricato, lo farà il primo boot"
		return
	fi
	if ! as_root nginx -t >/dev/null 2>&1; then
		warn "'nginx -t' fallisce: non ricarico nginx per non mandarlo giù. Controlla con 'sudo nginx -t'"
		return
	fi
	as_root systemctl reload nginx || warn "reload di nginx non riuscito"
}

ensure_update_manager_block() {
	local conf="$REPO_HOME/printer_data/config/moonraker.conf"

	if [ ! -e "$conf" ]; then
		warn "$conf non esiste: salto il blocco update_manager"
		return
	fi
	if [ -L "$conf" ]; then
		# In futuro moonraker.conf sarà un symlink dentro G2-Configs, cioè un file di cui la
		# fonte di verità è il repository delle configurazioni: scriverci sarebbe un
		# cambiamento occulto, e verrebbe comunque cancellato alla sincronizzazione
		# successiva (docs 04 — moonraker.conf è del repository).
		warn "moonraker.conf è un symlink (gestito dal repository delle configurazioni):" \
			"non lo tocco. Il blocco [update_manager G2-Service] deve stare nella copia pubblicata"
		return
	fi
	# Solo un'intestazione di sezione a inizio riga: il moonraker.conf di G2-OS ha un commento
	# "# [update_manager G2-Service] is appended by ...", e un grep sul testo semplice lo
	# prendeva per il blocco, che così non veniva mai aggiunto.
	if grep -qE '^\[update_manager G2-Service\]' "$conf"; then
		info "blocco [update_manager G2-Service] già presente"
		return
	fi

	if [ "$REPO_DIR" != "$REPO_HOME/G2-Service" ]; then
		warn "il repository è in $REPO_DIR e non in $REPO_HOME/G2-Service:" \
			"il blocco update_manager qui sotto punterà al posto sbagliato, correggilo a mano"
	fi

	info "aggiungo il blocco [update_manager G2-Service] a $conf"
	as_repo_user tee -a "$conf" >/dev/null <<'EOF'

[update_manager G2-Service]
type: git_repo
path: ~/G2-Service
origin: https://github.com/gingeradditive/G2-Service.git
primary_branch: main
managed_services: g2-service
virtualenv: ~/G2-Service/venv
requirements: requirements.txt
install_script: Scripts/install.sh
EOF
}

restart_service() {
	if ! systemd_running; then
		warn "systemd non è attivo (chroot di build): niente avvio adesso." \
			"Il servizio partirà al primo boot vero grazie a enable + WantedBy=multi-user.target"
		return
	fi

	info "riavvio $SERVICE_NAME"
	if ! as_root systemctl restart "$SERVICE_NAME"; then
		as_root journalctl -u "$SERVICE_NAME" -n 20 --no-pager || true
		fail "il servizio non è ripartito"
	fi
}

# ------------------------------------------------------------------ main

main() {
	[ "$(uname -s)" = "Linux" ] ||
		fail "install.sh gira solo su Linux. Per lo sviluppo locale vedi il README"
	[ -f "$REPO_DIR/requirements.txt" ] ||
		fail "$REPO_DIR non sembra il repository di G2-Service"

	REPO_USER="$(repo_user)"
	REPO_HOME="$(getent passwd "$REPO_USER" | cut -d: -f6)"
	[ -n "$REPO_HOME" ] || fail "home dell'utente $REPO_USER non trovata"

	info "installo da $REPO_DIR (utente $REPO_USER)"

	ensure_venv
	setup_matrix
	install_unit
	ensure_etc_dir
	install_nginx_location
	ensure_update_manager_block
	restart_service

	info "fatto. Stato: systemctl status $SERVICE_NAME — log: journalctl -u $SERVICE_NAME -f"
}

main "$@"
