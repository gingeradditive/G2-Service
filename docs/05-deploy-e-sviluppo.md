# 05 — Deploy, aggiornamenti e sviluppo locale

> Implementato, tranne `rundev.sh` (che resta da scrivere). L'unit systemd, la `location`
> nginx e `Scripts/install.sh` sono nel repository, sotto `Scripts/`.

## Porta e indirizzo

G2-Service ascolta su **`0.0.0.0:8000`**.

- **8000**, non 8080: sulla stessa macchina la porta 8080 è già occupata da **crowsnest** per lo
  stream della webcam (`modules/generic/files/mainsail-nginx/upstreams.conf` in G2-OS punta a
  `127.0.0.1:8080`). 8000 è anche il valore che GingerView usa già come default
  (`NETWORK_API_PORT`), quindi non c'è niente da riallineare su quel fronte.
- **`0.0.0.0`**, non solo `127.0.0.1`: in produzione GingerView passa comunque da nginx
  (same-origin), ma l'accesso diretto serve per il debug e per lo sviluppo di GingerView, dove
  il dev server sul portatile punta alla stampante reale. Nota che l'API non ha autenticazione e
  gira come root (vedi [02 — Privilegi](02-architettura.md#privilegi-ed-esecuzione)): è
  accettabile sulla rete locale di un laboratorio, non su una rete non fidata.

## Configurazione

Tutta da variabili d'ambiente, con default che funzionano senza configurare niente (`src/settings.py`).

| Variabile | Default in produzione | Default in sviluppo |
|---|---|---|
| `G2_SERVICE_HOST` | `0.0.0.0` | `0.0.0.0` |
| `G2_SERVICE_PORT` | `8000` | `8000` |
| `G2_SERVICE_MOCK` | `0` su Linux | `1` fuori da Linux |
| `G2_SERVICE_ETC_DIR` | `/etc/g2` | `.devdata/etc/g2` nel repo |
| `G2_SERVICE_PRINTER_DATA_DIR` | `/home/pi/printer_data` | `.devdata/printer_data` nel repo |

In mock i percorsi di sistema diventano cartelle dentro il repository: sviluppare non richiede
privilegi e non tocca niente sotto `/etc`.

`/home/pi/printer_data` è scritto per esteso e **non** derivato da `~`: il servizio gira come
root, quindi `~` sarebbe `/root`, mentre quella cartella appartiene a `pi` (vedi
[02 — Privilegi](02-architettura.md#privilegi-ed-esecuzione)).

Il prefisso `/service` **non** è configurabile: è una costante di `settings.py`, appaiata alla
regola nginx qui sotto. Poterlo cambiare da una variabile d'ambiente vorrebbe dire poter
rompere il routing senza accorgersene.

## Nginx

**Ogni servizio installa la propria configurazione.** Il site nginx resta di GingerView, ma non
deve più contenere le rotte di G2-Service: cambiare un path qui non deve richiedere una modifica
in un altro repository.

Il site di GingerView include una directory condivisa dentro il proprio blocco `server`:

```nginx
server {
    listen 80 default_server;
    # ...
    include /etc/nginx/g2-locations.d/*.conf;
    # ...
}
```

e `Scripts/install.sh` di G2-Service ci deposita il proprio file:

```nginx
# /etc/nginx/g2-locations.d/g2-service.conf
location ^~ /service/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Scheme $scheme;
    proxy_read_timeout 120;
}
```

Il prefisso `^~` ha la precedenza sulle `location` regex, quindi vince sulla regex di Moonraker
anche se questa venisse valutata prima. Una `include` con wildcard che non trova file non è un
errore per nginx, quindi il site di GingerView funziona anche su una macchina senza G2-Service.

`proxy_read_timeout` può restare basso perché **non ci sono richieste lunghe**: le operazioni
che durano sono job asincroni che rispondono subito
(vedi [02](02-architettura.md#operazioni-lunghe-modello-a-job-asincroni)).

> Serve una modifica in GingerView per aggiungere la riga `include`: è annotata nel suo
> `docs/TODO.md`.

## Aggiornamento tramite l'update_manager di Moonraker

G2-Service non ha un meccanismo di aggiornamento proprio: si aggiorna come Kalico, Crowsnest e
GingerView, tramite l'`update_manager` di Moonraker (`type: git_repo`). Moonraker confronta il
repository locale con `origin`, fa `git pull`, reinstalla le dipendenze, richiama lo script di
installazione e riavvia il servizio.

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

⚠️ Questo blocco vive in `moonraker.conf`, che è **sotto sincronizzazione da G2-Printers** (vedi
[04](04-proposta-api-configurazioni.md#moonrakerconf-è-del-repository)): la copia pubblicata nel
repository deve contenerlo, altrimenti la macchina perde la capacità di aggiornarsi.

## `Scripts/install.sh`

Invocato alla prima installazione dal modulo
[`modules/generic/69-G2-Service`](https://github.com/gingeradditive/G2-OS-dev/blob/main/modules/generic/69-G2-Service)
di G2-OS come `sudo -u pi bash ./Scripts/install.sh` — gira quindi **come utente `pi`**, con sudo
passwordless disponibile (default su Raspberry Pi OS). Lo stesso script è poi l'`install_script`
richiamato da Moonraker a ogni aggiornamento, quindi **deve essere idempotente**.

> Il repository dell'immagine è `gingeradditive/G2-OS-dev` (privato, branch `main`). Il vecchio
> `gingeradditive/G2-OS` è il primo tentativo, abbandonato: quello che c'è lì non gira più.

Responsabilità:

1. Creare/aggiornare il venv Python e installare `requirements.txt`.
2. Creare/aggiornare l'unit systemd `g2-service` (esecuzione **come root**, `uvicorn src.main:app
   --host 0.0.0.0 --port 8000`), abilitarla e riavviarla.
3. Depositare `/etc/nginx/g2-locations.d/g2-service.conf` (creando la directory se manca) e
   ricaricare nginx.
4. Creare `/etc/g2/` per il seriale e lo stato delle configurazioni.
5. Solo se assente, aggiungere il blocco `[update_manager G2-Service]` a
   `~/printer_data/config/moonraker.conf`, così che dagli aggiornamenti successivi se ne occupi
   Moonraker.

Va gestito il caso in cui lo script gira **dentro il chroot di build di G2-OS**, dove systemd non
è realmente attivo: `systemctl enable` funziona (è solo un symlink), `systemctl start/restart` no.
In quel contesto l'errore va tollerato e il servizio partirà al primo boot reale grazie a
`enable` + `WantedBy=multi-user.target`. Lo stesso vale per il reload di nginx.

Il rilevamento non è euristico: si guarda se esiste `/run/systemd/system`, il controllo canonico
per "systemd è davvero il PID 1" che usano anche i maintainer script di Debian. Quando c'è, un
`restart` fallito **fa fallire l'installazione** (con le ultime righe di `journalctl` in output);
quando non c'è, si salta il riavvio dicendolo. Ignorare gli errori in blocco nasconderebbe i
guasti veri sulla macchina vera.

### Il venv e il ripiego su `virtualenv`

`python3 -m venv` non funziona su Raspberry Pi OS senza il pacchetto `python3-venv`, che il
modulo `69-G2-Service` installa fra le sue `DEPS`. Lo script non ci fa comunque affidamento:
prova prima la libreria standard e ripiega su `virtualenv`, che sulla macchina c'è di sicuro
perché lo installa il modulo di Kalico ed è quello con cui Moonraker si crea il proprio venv. Il
ripiego copre le immagini costruite prima e i checkout fatti a mano.

Il venv appartiene all'utente che possiede il repository (`pi`), non a root: è come `pi` che
Moonraker reinstalla le dipendenze a ogni aggiornamento, e un venv di root gli sarebbe
inaccessibile.

### `DESTDIR`

Tutti i percorsi di sistema passano da `$DESTDIR`, vuoto in produzione, con la convenzione di
`make install`. Serve a esercitare lo script su una radice finta senza lasciargli toccare la
macchina — è il modo in cui sono stati verificati il ramo chroot, l'idempotenza e i casi di
`moonraker.conf`.

### Se manca la riga `include` in nginx

Lo script deposita comunque il proprio file e **avvisa** che finché il site di GingerView non
include `g2-locations.d/`, `/service/` non è raggiungibile dalla porta 80 (il servizio resta
raggiungibile sulla 8000). È la modifica annotata come `NET-5` nel TODO di GingerView.

### `moonraker.conf` che è un symlink

Se `moonraker.conf` è un symlink, lo script **non lo tocca** e lo dice: in quel caso il file
appartiene al repository delle configurazioni (vedi
[04](04-proposta-api-configurazioni.md#moonrakerconf-è-del-repository)), scriverci sarebbe un
cambiamento occulto e verrebbe comunque perso alla sincronizzazione successiva. Il blocco
`[update_manager G2-Service]` deve stare nella copia pubblicata.

## Il modulo `69-G2-Service` di G2-OS

Verificato contro l'`install.sh` attuale: **funziona senza modifiche**. Clona in
`/home/pi/G2-Service` (che è ciò che l'`update_manager` si aspetta) e invoca lo script come
utente `pi` dalla radice del repository, cioè esattamente le condizioni su cui è scritto.

Il clone è **anonimo**, perché `gingeradditive/G2-Service` è pubblico, e le `DEPS` sono `git` e
`python3-venv`. Il modulo gira **per ultimo** fra i generici, e non per caso: deposita una
location nginx in `g2-locations.d/`, che ha effetto solo se esiste già il site di GingerView
(`52-gingerview`), e appende il proprio blocco `update_manager` a `moonraker.conf`
(`51-moonraker`).

## `rundev.sh`

Script alla radice del repo per lo sviluppo locale, pensato per girare **anche su macOS**, senza
systemd né root: crea un venv locale, installa le dipendenze, avvia `uvicorn --reload`.

## Modalità mock

Serve perché il servizio è quasi tutto un involucro attorno a comandi che esistono solo su Linux
(`nmcli`, `timedatectl`) e attorno a GitHub. Si attiva con `G2_SERVICE_MOCK=1` (o `--mock`), e
**fuori da Linux si attiva da sola**: su macOS quei comandi non ci sono comunque.

Non è un semplice "restituisci qualcosa": ogni servizio ha un'implementazione mock che rispetta
la stessa interfaccia di quella reale (vedi
[02 — Organizzazione del codice](02-architettura.md#organizzazione-del-codice)) e restituisce dati
verosimili — un elenco di reti WiFi con segnali diversi, reti protette e aperte, una connessione
attiva, un fuso orario.

Il mock di rete tiene anche uno **stato**: connettersi cambia davvero ciò che risponde
`/service/network/status`, disconnettersi spegne l'autoconnect, dimenticare una rete la toglie
dall'elenco. Il giro completo si sviluppa quindi su macOS esattamente come sulla macchina vera.
I job finti durano qualche secondo di proposito: se finissero subito, il client non farebbe mai
in tempo a vederli `running` e quel percorso resterebbe non provato.

Deve poter simulare anche i **fallimenti**, altrimenti serve solo a sviluppare il caso felice
mentre i casi che rompono l'interfaccia restano non testabili. Una variabile
`G2_SERVICE_MOCK_SCENARIO` seleziona lo scenario: password sbagliata, nessuna rete trovata,
NetworkManager assente, GitHub irraggiungibile, seriale inesistente nel repository. È anche il
modo in cui si sviluppa GingerView contro un G2-Service finto senza avere una stampante sul banco.

## Test e qualità

Test proporzionati, non esaustivi: il valore sta dove il codice è fragile, cioè nel **parsing
dell'output di `nmcli`** (formato tabellare che cambia tra versioni, SSID con caratteri strani) e
nel **contratto degli endpoint** (che GingerView consuma). Entrambi si testano senza Raspberry Pi
grazie al livello mock.

- `pytest` + `httpx` per i test degli endpoint.
- `ruff` per lint e formattazione.
- Nessuna soglia di copertura, nessun `mypy` obbligatorio: la struttura conta più della
  percentuale.
