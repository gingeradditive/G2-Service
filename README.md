# G2-Service

Servizio di sistema della Stampante G2 (stampante 3D a pellet Ginger, basata su
[Kalico](https://github.com/KalicoCrew/kalico)/[Moonraker](https://github.com/Arksine/moonraker)
su Raspberry Pi 4). Si occupa di tutto ciò che riguarda l'host e che Moonraker non copre:
connessione di rete (WiFi/Ethernet), timezone di sistema e la matrice LED su cui la stampante
scrive i messaggi durante la stampa.

Per il dettaglio su scope e architettura vedi la [documentazione](docs/README.md).

## Avvio

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Fuori da Linux la **modalità mock** si attiva da sola (`nmcli` e `timedatectl` non esistono su
macOS) e i percorsi di sistema diventano `.devdata/` dentro il repository: non serve nessun
privilegio e non viene toccato niente sotto `/etc`. Si forza con `G2_SERVICE_MOCK=0|1`.

## API

Tutto sta sotto il prefisso `/service/`, Swagger compreso.

- Swagger UI: `/service/docs` — ReDoc: `/service/redoc`
- Health check: `GET /service/health`
- Rete: `GET /service/network/status`, `/network/wifi/networks`, `/network/wifi/saved`,
  `/network/ethernet/status`, più `POST /network/wifi/{rescan,connect,disconnect}` e
  `DELETE /network/wifi/saved/{ssid}`
- Fuso orario: `GET`/`POST /service/timezone`
- Stato di un'operazione asincrona: `GET /service/jobs/{jobId}`

Connessione e disconnessione WiFi sono **asincrone**: rispondono `202` con un job, perché
connettersi cambia l'indirizzo IP della macchina e fa cadere la richiesta in corso.

## Installazione sulla stampante

```bash
bash ./Scripts/install.sh
```

Idempotente: crea il venv, installa l'unit systemd, deposita la `location` nginx, crea
`/etc/g2/`, abilita SPI per la matrice LED e registra il servizio nell'update manager di
Moonraker. Lo invoca G2-OS alla
creazione dell'immagine e Moonraker a ogni aggiornamento. Vedi
[05 — Deploy](docs/05-deploy-e-sviluppo.md).

## Matrice LED

`matrix/run_display.sh` scrive un messaggio sulla matrice MAX7219 collegata via SPI. Non è
un'API: lo chiama Kalico con `gcode_shell_command`, e `install.sh` lo installa insieme al resto
(vedi [06 — Matrice LED](docs/06-matrice-led.md)).

```gcode
LED_MESSAGE MSG="STAMPA IN CORSO"
```

> Stato attuale: tutte le API sono implementate con la loro modalità mock, il deploy c'è e la
> matrice LED è nel repository. Manca la verifica su una macchina vera; le configurazioni
> stampante sono progettate nella [documentazione](docs/README.md) ma non ancora scritte.
