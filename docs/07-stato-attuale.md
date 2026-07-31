# 07 — Stato attuale e limiti noti

Fotografia onesta del repository al 30 luglio 2026, scritta confrontando `README.md`, gli
script e i commenti con quello che il codice in `src/` fa davvero. Serve a non riscoprire le
stesse cose due volte e a non scambiare un artefatto di refactoring per un bug nuovo. Dove
non ho potuto verificare su hardware reale, lo dico esplicitamente.

## Il README.md alla radice è in gran parte aspirazionale

`README.md` descrive: gestione impostazioni macchina (`/api/settings/*`), aggiornamenti
firmware (`/api/updates/*`), autenticazione JWT, un modello dati con SQLAlchemy/Alembic,
una cartella `tests/`, moduli `src/core/`, `src/models/`, `src/services/`, `src/utils/`, e
un file di config `Configs/printer.cfg` con sezioni `[server]`/`[printer]`/`[updates]` in
formato INI. **Nessuna di queste cose esiste nel codice.** Il repo implementa solo Wi-Fi e
Access Point (vedi [03](03-wifi-e-access-point.md)), più l'hosting della config macchina
Kalico (vedi [04](04-configurazione-macchina.md)).

Non è chiaro se sia un README scritto in anticipo per un piano poi non realizzato, o
copiato/adattato da un template generico. In ogni caso: **non fidarsi del README per capire
cosa fa il servizio**, usare questa cartella `docs/` o leggere `src/` direttamente.

Conseguenza pratica: `requirements.txt` installa `sqlalchemy`, `alembic`, `python-jose`,
`passlib`, `structlog`, `rich` — tutte dipendenze coerenti con quel README aspirazionale, non
importate da nessun file in `src/`.

## Incoerenze tra script e codice

### Nome del symlink config diverso da quello usato negli include

`Scripts/install.sh` crea il symlink di configurazione con il nome `G2-Configs`:

```bash
ln -sf "$(pwd)/Configs" ~/printer_data/config/G2-Configs
```

ma `printer.cfg` include i file con il prefisso `G2-Service/`:

```
[include G2-Service/mainsail.cfg]
[include G2-Service/macro.cfg]
[include G2-Service/main.cfg]
```

Ho cercato in tutto `G2-OS/modules/` un secondo symlink o directory chiamata `G2-Service`
dentro `printer_data/config/` (che risolverebbe la discrepanza) e non l'ho trovato — l'unico
posto che clona il repo lo fa in `/home/pi/G2-Service` (home directory, non dentro
`printer_data/config/`). Se l'analisi è corretta, Klipper non troverebbe questi tre include
sulla macchina reale. **Non verificato su hardware**: potrebbe esserci un passaggio manuale
non scriptato, o il `printer.cfg` locale osservato potrebbe essere una copia più vecchia del
formato include. Da controllare alla prossima occasione di lavorare sulla macchina fisica.

### Nome del servizio systemd incoerente tra install.sh e deploy.sh

`Scripts/install.sh` crea e abilita un unit chiamato **`g2-service`**. `Scripts/deploy.sh`,
dopo il `rsync`, riavvia via SSH un unit chiamato **`fastapi-app`**:

```bash
ssh pi@${DISCOVERY_HOST} "sudo systemctl restart fastapi-app"
```

I due nomi non corrispondono. Verosimilmente `deploy.sh` non è stato aggiornato quando il
servizio è stato rinominato (la cronologia git mostra un periodo iniziale di "bootstrapping
fastapi server" prima dell'introduzione del nome `g2-service`). Su una macchina installata
con lo script attuale, `deploy.sh` sincronizza i file ma il riavvio del servizio fallisce (o,
se un unit `fastapi-app` esiste ancora per altri motivi, riavvia la cosa sbagliata).

### Symlink deploy.sh rotto

Il file `deploy.sh` nella radice del repo è un symlink:

```
deploy.sh -> /Users/giacomoguaresi/Source/GingerRepos/G2-Service/Scripts/deploy.sh
```

Punta a un percorso che manca di un livello (`GingerRepos/G2-Service/...` invece di
`GingerRepos/G2/G2-Service/...`) — quasi certamente un residuo di quando questo repo viveva
direttamente sotto `GingerRepos/`, prima di essere spostato dentro la cartella `G2/`. È
rotto e specifico per il path locale di chi l'ha creato (non è portabile su un'altra
macchina anche se il target fosse corretto): da rimuovere o sostituire con l'invocazione
diretta di `Scripts/deploy.sh`.

### Riferimenti alla vecchia porta 8000

Il servizio ascolta su **8080** da diversi commit (era `8000` in origine — vedi il commit
`2794d9d`, "fix: update API service port from 8000 to 8080"). Sono rimasti però riferimenti
non aggiornati alla vecchia porta:

- `src/static/api-docs.html` (servito da `GET /docs-offline`) dichiara `Base URL:
  http://192.168.4.1:8000`;
- `GingerView/.env.example` documenta `VITE_NETWORK_API_PORT` con default `8000` (commentato,
  quindi non attivo di default, ma fuorviante se qualcuno lo decommenta guardando l'esempio).

### Docs-offline fuori sincrono

Oltre alla porta sbagliata, `src/static/api-docs.html` (servito da `/docs-offline`) elenca
un sottoinsieme datato degli endpoint reali: manca `GET /api/wifi/saved-networks` e
`POST /api/wifi/forget-network`; il DELETE è documentato come `/api/wifi/networks/{ssid}`
mentre la route reale è `/api/wifi/saved-networks/{ssid:path}` (vedi
[03](03-wifi-e-access-point.md)). Utile solo come promemoria approssimativo, non come
riferimento affidabile — per quello usare [03](03-wifi-e-access-point.md) o `/docs`.

### `test_wifi.py` legge una struttura di risposta che non esiste più

Lo script stampa `status.get("connection")` e `status.get("network")`, chiavi che
`NetworkManager.get_wifi_status()` non produce nella sua struttura attuale
(`adapter`/`ip`/`signal_info` — vedi [03](03-wifi-e-access-point.md)). Non genera errori,
semplicemente quei blocchi di stampa restano sempre vuoti: uno script che sembra testare più
di quanto testi davvero.

## Fragilità nel codice

- **Fallback silenzioso a dati finti anche in produzione.** `NetworkManager.get_visible_networks()`
  restituisce reti Wi-Fi mock (`TestNetwork_1`, `TestNetwork_2`, `GuestNetwork`) ogni volta
  che sia `nmcli` sia `iwlist` falliscono — non solo in sviluppo su macOS, ma anche su una
  Raspberry Pi reale se ad esempio NetworkManager non è avviato. La risposta HTTP non
  distingue i due casi: chi consuma l'API (GingerView) non ha modo di sapere se sta vedendo
  reti reali o placeholder. Vedi [02](02-architettura.md#networkmanager-srcapinetworkpy).
- **`create_app(config_path=...)` ignora il parametro.** `src/server.py` espone `--config`
  e lo passa a `create_app`, ma la funzione non lo legge mai. L'opzione è inerte.
- **`src/server.py` non risulta usato da nessuno script.** `install.sh` avvia il servizio con
  `python src/main.py`, non `src/server.py` — nonostante quest'ultimo sia quello con opzioni
  da riga di comando pensate per la produzione (`--workers`, `--host`, `--port`).
- **Parsing testuale dell'output `nmcli`** basato su split su tab/`:` senza quoting — un SSID
  contenente uno di questi caratteri romperebbe il parsing (`_get_networks_nmcli`,
  `get_wifi_status`, `get_saved_networks` in `src/api/network.py`).
- **Possibile artefatto in `printer.cfg`.** La copia locale osservata ha una riga sospetta
  subito dopo il commento `Auto Setup` (fine del file, prima del blocco `SAVE_CONFIG`):
  `############################### Auto Setup #################################""")` — il
  `""")` finale sembra un frammento di codice Python incollato per errore durante un editing.
  Klipper tollera commenti arbitrari dopo `#`, quindi probabilmente non causa un errore di
  parsing, ma vale la pena ripulirlo alla prossima occasione, essendo `printer.cfg` un file
  non versionato e quindi facile da correggere senza impatto su altre macchine.

## Sicurezza

- **Nessun endpoint richiede autenticazione** — accettabile solo finché il servizio resta
  raggiungibile esclusivamente da LAN locale o dall'Access Point di setup, mai esposto su
  internet. Vedi anche [03](03-wifi-e-access-point.md#note-generali).
- **CORS aperto a tutte le origini** (`allow_origins=["*"]` in `src/api/app.py`), coerente
  con l'uso previsto ma da rivedere se cambiasse il modello di esposizione.
- Il servizio gira come **root** in produzione (vedi [06](06-deploy.md)) — necessario per
  eseguire comandi di rete privilegiati, ma significa che qualunque vulnerabilità nell'API
  ha impatto massimo sul sistema.
- Le credenziali dell'Access Point (`/home/pi/ap_credentials.txt`) sono leggibili da
  chiunque abbia accesso al filesystem e, tramite `GET /api/access-point/info`, da chiunque
  raggiunga l'API — coerente con lo scopo (un hotspot di setup temporaneo), non pensato per
  restare segreto a lungo termine.

## Da verificare (non confermato)

- **Possibile collisione sulla porta 8080.** Il template nginx ereditato da MainsailOS
  (`G2-OS/modules/generic/files/mainsail-nginx/upstreams.conf`) assegna la porta `8080` allo
  stream della webcam (`mjpgstreamer1`, servita da Crowsnest), la stessa porta su cui
  G2-Service ascolta (`0.0.0.0:8080`). Non ho verificato se questo file `upstreams.conf` sia
  ancora usato attivo così com'è nell'immagine G2-OS attuale (il top-level
  [G2/README.md](../../README.md) nota che nginx è stato riconfigurato per servire
  GingerView al posto di Mainsail, quindi il file potrebbe essere stato modificato o
  disattivato) — da controllare quando si lavora su G2-OS o su una macchina reale.
