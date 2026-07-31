# 02 — Architettura

## Struttura reale del repository

```
G2-Service/
├── src/
│   ├── main.py            # entry point di sviluppo (uvicorn diretto, porta 8080)
│   ├── server.py          # entry point di produzione (argparse: --host --port --workers --config)
│   ├── api/
│   │   ├── app.py         # application factory create_app(): tutte le route vivono qui
│   │   └── network.py     # NetworkManager: wrapper attorno a nmcli/iwlist per il Wi-Fi
│   └── static/
│       └── api-docs.html  # pagina di documentazione offline servita da /docs-offline
├── Configs/                # macro Klipper/Kalico della macchina (vedi 04)
├── Scripts/                 # install, deploy, setup Access Point (vedi 06)
├── docs/                    # questa documentazione
├── printer.cfg              # config Klipper "vero", non tracciato in git (vedi 04)
├── debug.py                  # avvio con auto-reload per lo sviluppo
├── test_wifi.py               # script manuale per testare NetworkManager
├── deploy.sh                   # symlink rotto verso Scripts/deploy.sh (vedi 07)
└── requirements.txt
```

Non esistono `src/core/`, `src/models/`, `src/services/`, `src/utils/` né `tests/`: sono
descritti nel `README.md` alla radice ma non nel repository.

## Application factory

`src/api/app.py` espone `create_app(config_path: str = None) -> FastAPI`. Il parametro
`config_path` è accettato ma **non viene mai letto** all'interno della funzione — è un
parametro morto, propagato da `server.py --config` senza alcun effetto osservabile.

`create_app()`:

- crea/monta `src/static/` su `/static` (asset per la doc offline);
- abilita CORS aperto a tutte le origini (`allow_origins=["*"]`) — coerente con un servizio
  che gira solo in LAN/AP locale, non pensato per essere esposto su internet;
- istanzia un singolo `NetworkManager()` condiviso da tutte le route Wi-Fi;
- registra le route elencate sotto.

## Entry point

| File | Uso | Dettagli |
|---|---|---|
| `src/main.py` | Avvio diretto (`python src/main.py`) | Uvicorn hardcoded su `0.0.0.0:8080`, `reload=False`. È anche l'entry point usato dal service systemd in produzione (`ExecStart=... python src/main.py`, vedi [06](06-deploy.md)) — nonostante esista `server.py` pensato apparentemente per quel ruolo. |
| `src/server.py` | Avvio con opzioni (`python src/server.py --host --port --workers --config`) | Non risulta invocato da nessuno script di `Scripts/`; `--config` non ha effetto (vedi sopra). |
| `debug.py` | Sviluppo locale | Usa `uvicorn.run("src.api.app:create_app", factory=True, reload=True, reload_dirs=["src"])`, log level `debug`. Bind su `localhost` (non `0.0.0.0`). |

## Endpoint esposti

Tutti definiti in `src/api/app.py`. Nessuno richiede autenticazione.

| Metodo | Path | Cosa fa |
|---|---|---|
| GET | `/` | Info di base (nome, versione) |
| GET | `/health` | Health check |
| GET | `/docs`, `/redoc` | Swagger UI / ReDoc generati da FastAPI (richiedono internet per gli asset CDN, salvo quanto sotto) |
| GET | `/docs-offline` | Pagina HTML statica (`src/static/api-docs.html`) con l'elenco endpoint, utilizzabile senza connessione internet — vedi [07](07-stato-attuale.md#docs-offline-fuori-sincrono) per i disallineamenti noti |
| GET | `/api/wifi/networks` | Scansione reti Wi-Fi visibili |
| GET | `/api/wifi/status` | Stato dell'adattatore Wi-Fi (device, IP, segnale) |
| POST | `/api/wifi/rescan` | Forza una nuova scansione |
| POST | `/api/wifi/connect` | Connessione a una rete (con o senza password) |
| POST | `/api/wifi/disconnect` | Disconnessione dalla rete corrente |
| GET | `/api/wifi/saved-networks` | Elenco reti salvate in NetworkManager |
| DELETE | `/api/wifi/saved-networks/{ssid}` | Elimina una rete salvata |
| POST | `/api/wifi/forget-network` | Alias semantico di delete (stesso codice, messaggi diversi) |
| GET | `/api/access-point/info` | Credenziali e stato dell'Access Point di setup (`wlan0`) |

Dettaglio completo di richieste/risposte in [03 — Wi-Fi e Access Point](03-wifi-e-access-point.md).

## NetworkManager (`src/api/network.py`)

Classe che incapsula tutte le chiamate di sistema per il Wi-Fi, eseguite via `subprocess` +
`nmcli` (path assoluto `/usr/bin/nmcli`). Punti da tenere a mente:

- **Due interfacce con ruoli fissi e hardcoded**: `wlan1` per la gestione Wi-Fi client
  (tutto ciò che passa da `NetworkManager`), `wlan0` per l'Access Point di setup (gestito
  fuori da NetworkManager, via `hostapd`/`dnsmasq` — vedi [06](06-deploy.md)). Ogni metodo
  Wi-Fi chiama `_validate_wlan1()` all'inizio e solleva eccezione se l'interfaccia non
  esiste.
- **Catena di fallback per la scansione** (`get_visible_networks`): prova `nmcli` → se fallisce
  prova `iwlist scan` → se fallisce anche quello, **restituisce reti finte** (`TestNetwork_1`,
  `TestNetwork_2`, `GuestNetwork`). Questo terzo livello è pensato per sviluppare su macOS,
  ma si attiva silenziosamente ogni volta che sia `nmcli` sia `iwlist` falliscono — anche in
  produzione, se ad esempio NetworkManager non è in esecuzione. Non c'è modo di distinguere
  dati reali da dati finti dalla risposta HTTP.
- **Parsing testuale fragile**: l'output di `nmcli -t` viene diviso su tab o `:` a seconda di
  cosa trova nella riga (`_get_networks_nmcli`, `get_wifi_status`, `get_saved_networks`) — un
  SSID contenente `:` romperebbe il parsing.
- **`use_sudo`**: alcuni comandi (`rescan`, `connect`, `disconnect`, `delete`) vengono
  eseguiti con `sudo` anteposto; altri (lettura) no. Il servizio in produzione gira comunque
  come `root` (vedi [06](06-deploy.md)), quindi `sudo` è ridondante ma innocuo lì; è
  necessario invece se in futuro il servizio venisse fatto girare con un utente non
  privilegiato.
- **`get_wlan0_ap_status()`**: unico punto che tocca `wlan0`. Controlla se `hostapd` è
  attivo e, se lo è ma l'interfaccia ha perso l'IP (può succedere se NetworkManager la
  reclama), la ripristina al volo (`ip addr add 192.168.4.1/24 ...`).

## Come si inserisce nel resto dello stack

Durante il **setup iniziale** (Access Point attivo), `Scripts/setup_wifi_complete.sh` genera
un vhost nginx dedicato su `192.168.4.1:80` che fa da reverse proxy verso i servizi locali:
Mainsail/GingerView sulla root, G2-Service dietro `/g2/` e `/docs` (verso `127.0.0.1:8080`),
Moonraker dietro `/api`, `/printer`, `/websocket` (verso `127.0.0.1:7125`). Vedi
[06 — Deploy](06-deploy.md) per il flusso completo.

In **funzionamento normale** (macchina già collegata alla rete Wi-Fi dell'utente), G2-Service
risponde direttamente sulla porta 8080; il proxy nginx di produzione (servito dall'immagine
G2-OS, non da questo repo) è quello che espone same-origin gli endpoint di Moonraker/GingerView
— non è stato verificato in questo repo se instrada anche `/api/wifi/*` verso G2-Service o se
GingerView lo raggiunge con un host/porta espliciti in quella modalità (vedi
`GingerView/.env.example`, variabili `VITE_NETWORK_API_*`).
