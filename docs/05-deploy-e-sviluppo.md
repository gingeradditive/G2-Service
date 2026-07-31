# 05 — Deploy, aggiornamenti e sviluppo locale

> Design deciso, **non implementato**. Nessuno script esiste ancora nel repo. Va scritto solo su
> richiesta esplicita.

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
[`G2-OS/modules/generic/69-G2-Service`](https://github.com/gingeradditive/G2-OS/blob/main/modules/generic/69-G2-Service)
come `sudo -u pi bash ./Scripts/install.sh` — gira quindi **come utente `pi`**, con sudo
passwordless disponibile (default su Raspberry Pi OS). Lo stesso script è poi l'`install_script`
richiamato da Moonraker a ogni aggiornamento, quindi **deve essere idempotente**.

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
