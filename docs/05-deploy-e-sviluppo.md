# 05 — Deploy, aggiornamenti e sviluppo locale

> Design deciso, **non implementato**. Nessuno script esiste ancora nel repo — vedi
> [02 — Architettura](02-architettura.md#stato-attuale). Va scritto solo su richiesta esplicita.

## Aggiornamento tramite l'update_manager di Moonraker

G2-Service non ha un meccanismo di aggiornamento proprio: si aggiorna nello stesso modo di
Kalico, Crowsnest e GingerView, tramite l'`update_manager` di Moonraker (`type: git_repo`).
Moonraker confronta periodicamente (o su richiesta) il repository locale con `origin`, e se ci
sono commit nuovi fa `git pull` e poi richiama uno script di installazione del componente
stesso, infine riavvia il servizio indicato in `managed_services`.

Il blocco da aggiungere a `moonraker.conf` (stesso formato già usato per Kalico/GingerView in
`G2-OS/modules/generic/files/moonraker.conf`):

```ini
[update_manager G2-Service]
type: git_repo
path: ~/G2-Service
origin: https://github.com/gingeradditive/G2-Service.git
primary_branch: main
managed_services: g2-service
virtualenv: ~/G2-Service/venv
requirements: requirements.txt
install_script: Scripts/install.sh
```

- `managed_services: g2-service` — presuppone che G2-Service giri come **servizio systemd**
  chiamato `g2-service` (non definito ancora, vedi sotto).
- `virtualenv` + `requirements` — dicono a Moonraker di reinstallare le dipendenze Python nel
  venv dopo ogni `git pull`, senza bisogno che lo faccia `install_script`.
- `install_script: Scripts/install.sh` — Moonraker lo rilancia dopo ogni pull, per tutto ciò
  che reinstallare i requirements non copre (es. modifiche al file di unit systemd). **Deve
  essere idempotente**: lo stesso script serve sia per la prima installazione sia per ogni
  aggiornamento successivo.

## `Scripts/install.sh`

Compatibile con il modo in cui lo invoca
[`G2-OS/modules/generic/69-G2-Service`](https://github.com/gingeradditive/G2-OS/blob/main/modules/generic/69-G2-Service)
alla prima installazione (`sudo -u pi bash ./Scripts/install.sh`, quindi **gira come utente
`pi`, non root** — richiede sudo passwordless per le operazioni privilegiate, il default su
Raspberry Pi OS per l'utente `pi`).

Responsabilità, entrambe da eseguire in modo idempotente (rieseguibile senza effetti
collaterali):

1. Creare/aggiornare il venv Python e installare `requirements.txt`.
2. Creare/aggiornare il servizio systemd `g2-service` (unit `ExecStart` verso
   `venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8080`), abilitarlo e (ri)avviarlo.
3. La **prima volta**, se non già presente, aggiungere il blocco `[update_manager G2-Service]`
   sopra a `~/printer_data/config/moonraker.conf` — dopodiché è Moonraker stesso a richiamare
   lo script a ogni update successivo, non serve più farlo da `69-G2-Service`.

Va gestito con attenzione il caso in cui lo script gira **dentro il chroot di build di G2-OS**
(dove systemd non è realmente attivo): `systemctl enable` funziona anche lì (è solo un
symlink), ma `systemctl start/restart` no — in quel contesto va tollerato l'errore e lasciato
che il servizio parta al primo boot reale grazie a `enable` + `WantedBy=multi-user.target`.

## `rundev.sh`

Script alla radice del repo per lo sviluppo locale, pensato per girare **anche su macOS**
(oltre che su Linux), senza systemd né privilegi di root:

- crea un venv locale (separato da quello di produzione), installa `requirements.txt`;
- avvia `uvicorn src.main:app --reload` su una porta di sviluppo;
- supporta una **modalità mock** (flag `--mock`, o variabile d'ambiente
  `G2_SERVICE_MOCK=1`), perché le integrazioni con tool solo-Linux (`nmcli`, `timedatectl`,
  ...) non implementate ancora dovranno, quando arriveranno, restituire dati finti invece di
  invocare quei comandi se questa variabile è impostata. **Fuori da Linux (es. macOS) il mock
  si attiva automaticamente**, dato che quei comandi non esistono comunque sulla macchina di
  sviluppo.

`G2_SERVICE_MOCK` è quindi la convenzione a cui le future implementazioni di
[03](03-proposta-api-rete-timezone.md) e [04](04-proposta-api-configurazioni.md) dovranno
attenersi per restare testabili in locale.
