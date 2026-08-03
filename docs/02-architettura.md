# 02 — Architettura

## G2-Service nello stack G2

Tutto gira sullo stesso Raspberry Pi 4 (G2-OS), come processi separati:

```
Raspberry Pi 4 (G2-OS)
├── Kalico           firmware (fork Klipper) — comunica con la scheda via UART
├── Moonraker        API/websocket per Kalico — stato macchina, file, macro, update manager
├── GingerView       interfaccia utente della macchina (SPA statica) — sostituisce
│                     integralmente Mainsail, parla con Moonraker e con G2-Service, non
│                     con Kalico direttamente
├── Crowsnest        streaming webcam (occupa la porta 8080 in locale)
├── Nginx            reverse proxy, punto d'ingresso unico sulla porta 80
└── G2-Service       questo progetto — API di sistema dell'host (porta 8000)
```

G2-Service non dipende da Kalico e non viene richiamato da nessuno degli altri componenti:
comunica direttamente con il sistema operativo del Raspberry Pi (NetworkManager,
`timedatectl`, ...). **Una dipendenza verso Moonraker esiste**, in una sola direzione e per un
solo scopo: dopo aver sincronizzato le configurazioni, G2-Service chiede a Moonraker di
riavviare Kalico (vedi [04](04-proposta-api-configurazioni.md#applicazione-e-riavvio)).

## Stack tecnico

| Livello | Tecnologia |
|---|---|
| Linguaggio | Python 3.11 (quello di Raspberry Pi OS Bookworm) |
| Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Server ASGI | [uvicorn](https://www.uvicorn.org/) |
| Documentazione API | Swagger UI e ReDoc generati da FastAPI, esposti sotto il prefisso `/service` (vedi sotto) |
| Client HTTP (verso GitHub) | `httpx` |
| Qualità | `ruff` per lint e formattazione, `pytest` per i test |

## Convenzioni comuni a tutte le API

Valgono per ogni endpoint, in [03](03-proposta-api-rete-timezone.md) e in
[04](04-proposta-api-configurazioni.md).

### Prefisso `/service`

**Tutti** gli endpoint stanno sotto `/service/…`, Swagger incluso
(`/service/docs`, `/service/redoc`, `/service/openapi.json`).

Il motivo è il routing nginx: `/api/`, `/printer/`, `/machine/`, `/server/` e `/access/`
appartengono a **Moonraker**, che li riceve tramite una `location` regex nel site nginx. Usare
`/api/…` costringerebbe ad aggiungere un'eccezione `^~` per ogni namespace di G2-Service, in un
file che vive in un altro repository. Con un prefisso tutto nostro basta **una sola** regola
nginx, valida per sempre (vedi [05](05-deploy-e-sviluppo.md#nginx)).

> ⚠️ `/service/` (nostro) e `/server/` (Moonraker) si assomigliano molto. Chi mette mano alla
> configurazione nginx deve fare attenzione a non confonderli: sono due destinazioni diverse.

### Nessun versionamento nell'URL

Niente `/service/v1/…`. L'unico client è GingerView, aggiornato insieme al servizio sulla
stessa macchina: versionare sarebbe sovrastruttura. Se un giorno un client esterno
(GingerSlicer) dovesse dipendere dal contratto, si valuterà allora.

### `camelCase` in tutti i corpi JSON

Richieste e risposte usano `camelCase` (`signalStrength`, `ntpSynchronized`), mai `snake_case`.

### Nessuna autenticazione

Coerente con Moonraker su G2-OS, che gira senza auth sulla stessa macchina.

### Modello degli errori

Due forme distinte, entrambe sotto la chiave `detail` (il default di FastAPI):

**1. Errori di validazione** — generati automaticamente da FastAPI, HTTP `422`:

```json
{ "detail": [ { "loc": ["body", "timezone"], "msg": "...", "type": "..." } ] }
```

**2. Errori applicativi** — sollevati da noi, con un codice stabile leggibile dal client:

```json
{ "detail": { "code": "SYSTEM_TOOL_UNAVAILABLE", "message": "nmcli non disponibile" } }
```

Quando usare quale codice HTTP:

| HTTP | `code` | Quando |
|---|---|---|
| 400 | `INVALID_INPUT` | Input sintatticamente valido ma non accettabile (es. timezone inesistente) |
| 404 | `NOT_FOUND` | La risorsa indicata non esiste (rete salvata, job) |
| 409 | `CONFLICT` | Un'operazione dello stesso tipo è già in corso |
| 502 | `UPSTREAM_UNAVAILABLE` | Un servizio esterno non risponde (GitHub) |
| 503 | `SYSTEM_TOOL_UNAVAILABLE` | Un comando di sistema manca o NetworkManager è giù |
| 500 | `INTERNAL_ERROR` | Tutto il resto (bug) |

**Gli esiti negativi previsti di un'operazione non sono errori HTTP.** Una password WiFi
sbagliata non è un 4xx: l'operazione è stata accettata ed eseguita correttamente, ha solo dato
esito negativo. Siccome le operazioni lunghe sono asincrone (sotto), quell'esito arriva come
`status: "failed"` del job, con un proprio codice: `WIFI_AUTH_FAILED`,
`WIFI_NETWORK_NOT_FOUND`, `WIFI_TIMEOUT`, `CONFIG_SERIAL_NOT_SET`, `CONFIG_SERIAL_NOT_FOUND`,
`CONFIG_DOWNLOAD_FAILED`, `CONFIG_RESTART_FAILED`.

### Operazioni lunghe: modello a job asincroni

Le operazioni che possono superare qualche secondo **non** rispondono in modo sincrono.
Restituiscono `202 Accepted` con l'identificativo di un job, e il client segue l'avanzamento
interrogandolo.

Sono asincrone: `POST /service/network/wifi/connect`,
`POST /service/network/wifi/disconnect`, `POST /service/config/sync`.
Tutto il resto (letture di stato, scansioni, timezone, rescan, dimentica rete) è sincrono.

Il motivo non è solo la durata. Connettersi a una rete WiFi **cambia l'indirizzo IP della
macchina**: la connessione HTTP su cui è arrivata la richiesta cade prima che una risposta
sincrona possa tornare indietro. Il client non saprebbe mai com'è andata. Con un job, il
client si riconnette al nuovo indirizzo e legge l'esito.

```
POST /service/network/wifi/connect      →  202  { "jobId": "...", "type": "wifi.connect",
                                                  "status": "running", "startedAt": "..." }

GET  /service/jobs/{jobId}              →  200  { "jobId": "...", "type": "wifi.connect",
                                                  "status": "succeeded",
                                                  "startedAt": "...", "finishedAt": "...",
                                                  "result": { ... } }
```

- `status`: `running` | `succeeded` | `failed`.
- In caso di fallimento: `"error": { "code": "WIFI_AUTH_FAILED", "message": "..." }`.
- I job vivono **in memoria**, con scadenza dopo un'ora: non serve persistenza, e dopo un
  riavvio del servizio l'unica cosa che conta è lo stato reale del sistema, interrogabile con
  gli endpoint di stato.
- Un solo job per tipo alla volta: una seconda richiesta dello stesso tipo mentre la prima è
  in corso riceve `409 CONFLICT`.
- `GET /service/jobs/{jobId}` su un id sconosciuto o scaduto: `404 NOT_FOUND`.
- La scadenza si conta **dalla fine**: un job ancora in corso non scade, altrimenti
  un'operazione lenta perderebbe il proprio risultato proprio mentre lo produce.
- Un errore applicativo sollevato *dentro* un job non ha nessuna risposta HTTP in cui finire e
  diventa l'esito negativo del job, conservando il proprio codice: se NetworkManager cade a
  metà di una connessione il job dice `SYSTEM_TOOL_UNAVAILABLE`, non un generico errore
  interno.

## Privilegi ed esecuzione

Il servizio gira **come root**. Le operazioni che deve compiere (modificare connessioni
NetworkManager, `timedatectl set-timezone`, scrivere in `/etc/g2/`, scrivere nella cartella
delle configurazioni) richiedono privilegi, e una whitelist `sudoers` che le coprisse tutte
sarebbe lunga, fragile e da mantenere allineata in G2-OS.

È un compromesso consapevole, non una scelta indolore: un'API **senza autenticazione**, in
ascolto su tutte le interfacce, gira con i massimi privilegi. Sulla rete locale di un
laboratorio è accettabile (Moonraker sulla stessa macchina è già senza auth e può muovere la
stampante); se un giorno la macchina dovesse essere esposta a una rete non fidata, questa è la
prima cosa da rivedere.

**Conseguenza pratica da non dimenticare**: i file che G2-Service scrive dentro
`~/printer_data/` nascerebbero di proprietà di `root`, ma Moonraker gira come utente `pi` e
deve poterli modificare (l'editor di configurazione di GingerView passa da lì). Ogni file
scritto sotto `printer_data` va quindi riportato a `pi:pi`.

## Organizzazione del codice

```
src/
├── main.py              creazione dell'app, montaggio dei router sotto /service
├── settings.py          configurazione da variabili d'ambiente (porta, mock, percorsi)
├── errors.py            eccezioni applicative e traduzione in risposte HTTP
├── dependencies.py      i `Depends` con cui i router ricevono i servizi
├── routers/             un modulo per area — solo HTTP: validazione, codici, nessuna logica
│   ├── health.py
│   ├── network.py
│   ├── timezone.py
│   ├── jobs.py          stato dei job asincroni
│   ├── factory.py       seriale di fabbrica — parte 2
│   └── configs.py       sincronizzazione da G2-Printers — parte 2
├── services/            la logica vera; ogni area ha un'implementazione reale e una mock
│   ├── container.py     scelta reale/mock all'avvio
│   ├── system.py        esecuzione dei comandi di sistema: timeout e traduzione degli errori
│   ├── jobs.py          esecuzione e registro dei job
│   ├── health/          i check di /service/health
│   ├── network/         WiFi ed Ethernet
│   │   └── nmcli.py     comandi e parsing, isolati e verificabili su output finto
│   ├── timezone/        timedatectl
│   └── configs/         GitHub + filesystem + riavvio via Moonraker — parte 2
└── models/              schemi Pydantic di richiesta e risposta
    └── base.py          `CamelModel`, da cui discendono tutti gli schemi
```

La regola che tiene in piedi la struttura: **i router non eseguono comandi di sistema**, si
limitano a chiamare un servizio. Ogni servizio espone un'interfaccia (un `Protocol`) con due
implementazioni, quella reale e quella mock, scelte all'avvio in base a `G2_SERVICE_MOCK` e
iniettate nei router con `Depends`. È ciò che rende il progetto sviluppabile su macOS e
testabile senza un Raspberry Pi (vedi [05](05-deploy-e-sviluppo.md#modalità-mock)).

Ogni area di servizio è una cartella con la stessa forma — `__init__.py` per il `Protocol`,
`real.py` e `mock.py` per le due implementazioni. `services/health/` è l'esempio più piccolo e
fa da modello per le altre. Le implementazioni **non ereditano** dal `Protocol`: la conformità
è strutturale, ed è `build_services()` in `services/container.py` a dichiarare il tipo che
restituisce. `container.py` è anche l'unico punto del progetto che sa se si sta girando in mock
o sul ferro: da lì in poi i router vedono solo interfacce.

Il `camelCase` non si ripete campo per campo: sta nell'alias generator di `CamelModel`
(`models/base.py`), da cui discendono tutti gli schemi.

## Stato attuale

Il progetto non è mai arrivato in produzione ed è stato azzerato: la versione precedente
(gestione WiFi via `nmcli`, Access Point, script di deploy/systemd, config Klipper/Mainsail
committate nel repo) è stata rimossa — resta consultabile nella cronologia git se serve come
riferimento, ma non va considerata uno stato da cui ripartire.

Oggi ci sono la struttura descritta in questo documento — prefisso `/service`, modello degli
errori, infrastruttura dei job asincroni, selezione reale/mock — e **tutti gli endpoint di
[03](03-proposta-api-rete-timezone.md)**: health, rete (WiFi ed Ethernet) e fuso orario, ognuno
con la propria implementazione mock. È l'intero scope della parte 1 sul fronte API.

C'è anche il deploy: unit systemd, `location` nginx e `Scripts/install.sh` (vedi
[05](05-deploy-e-sviluppo.md)). Quello che manca è la verifica **sulla macchina vera**: finora
tutto è stato provato con implementazioni mock e comandi di sistema finti, e il formato reale
di `nmcli` e `timedatectl` non è ancora stato visto.

Le configurazioni stampante restano progettate ma **non implementate**: la cartella
`services/configs/` non esiste ancora.

## Struttura del repository

```
G2-Service/
├── README.md
├── requirements.txt
├── rundev.sh          sviluppo locale (anche macOS, con mock) — da scrivere
├── Scripts/
│   ├── install.sh              installazione e aggiornamento su Raspberry Pi
│   ├── g2-service.service      unit systemd (`__REPO_DIR__` sostituito da install.sh)
│   └── g2-service.nginx.conf   la `location ^~ /service/` depositata in g2-locations.d/
├── docs/
├── src/               vedi "Organizzazione del codice"
└── .devdata/          sostituto locale di /etc/g2 e printer_data in sviluppo — non versionato
```
