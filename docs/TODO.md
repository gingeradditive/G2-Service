# TODO

Solo le cose da fare. Quando un task è completato viene **rimosso** da qui: quello che è già
stato fatto si legge nella documentazione (`01`–`05`), non in questo file.

**Codici.** Ogni task ha un codice `AREA-n` con cui puoi farvi riferimento rapidamente
("fai CORE-1", "NET-4 è bloccato"). I codici sono **stabili e non vengono mai riusati**:
l'area indica l'argomento, non lo stato, così un task che si sblocca mantiene il suo codice.

**Formato.** Una riga per task: `` `CODICE` `` + descrizione + stato in fondo. Lo stato è
`— pronto` (si può iniziare), `— dipende da CODICE` (bloccato da un altro task) oppure
`→ Qn` (bloccato dalla domanda corrispondente in [Q&A.md](Q&A.md)).

**Aree.**

- `CORE` — struttura del progetto e convenzioni trasversali
- `NET` — rete WiFi ed Ethernet
- `TZ` — fuso orario
- `DEP` — deploy, systemd, nginx, aggiornamenti
- `DEV` — sviluppo locale, mock, test
- `INT` — verifica su hardware reale e con GingerView
- `FAC` — seriale di fabbrica *(parte 2)*
- `CFG` — configurazioni da G2-Printers *(parte 2)*
- `AP` — onboarding di rete via Access Point *(parte 2)*

**Stato di partenza.** Nel repository c'è solo `src/main.py` con `GET /health`. Tutto ciò che
segue è da scrivere.

---

# Parte 1 — Implementazione corrente

Copre lo scope attuale: rete, fuso orario, e tutto ciò che serve per far girare e aggiornare il
servizio su una macchina vera.

**Ordine consigliato.** `CORE-1` → `CORE-6` prima di tutto: definiscono la struttura su cui si
appoggia il resto, e rifarli dopo costerebbe molto di più. Poi `NET` e `TZ` in parallelo (sono
indipendenti), poi `DEP` per portarlo sulla macchina, infine `INT` per verificarlo davvero.
`DEV-1` conviene anticiparlo: senza `rundev.sh` si sviluppa scomodi fin dal primo giorno.

## CORE — Struttura e convenzioni

- `CORE-1` Creare la struttura decisa in [02](02-architettura.md#organizzazione-del-codice): `routers/`, `services/`, `models/`, `settings.py`. I router non eseguono comandi di sistema, chiamano un servizio — pronto
- `CORE-2` `settings.py`: configurazione da variabili d'ambiente (porta, `G2_SERVICE_MOCK`, percorsi di `/etc/g2` e `printer_data`), con valori di default utilizzabili in sviluppo — dipende da `CORE-1`
- `CORE-3` Montare **tutto** sotto il prefisso `/service`, Swagger compreso (`docs_url`, `redoc_url`, `openapi_url`), e spostare l'endpoint esistente da `/health` a `/service/health` — dipende da `CORE-1`
- `CORE-4` Modello degli errori di [02](02-architettura.md#modello-degli-errori): una gerarchia di eccezioni applicative con `code`, e un exception handler che le traduce in `{"detail": {"code", "message"}}` con lo status giusto. Gli errori di validazione restano quelli di FastAPI — dipende da `CORE-1`
- `CORE-5` Infrastruttura dei job asincroni: registro in memoria, `status` `running`/`succeeded`/`failed`, scadenza dopo un'ora, un solo job per tipo (`409 CONFLICT` sul secondo), `GET /service/jobs/{jobId}` con `404` su id sconosciuto o scaduto — dipende da `CORE-4`
- `CORE-6` Selezione fra implementazione reale e mock: ogni servizio dietro un `Protocol`, scelta all'avvio in base a `G2_SERVICE_MOCK` e iniezione nei router con `Depends`. Il mock si attiva da solo fuori da Linux — dipende da `CORE-1`
- `CORE-7` Arricchire `/service/health` con `version` e `checks` (`networkManager`, `timedatectl`, `serialConfigured`); `status` resta `"ok"` anche con qualche check a `false` — dipende da `CORE-3`

## NET — Rete

- `NET-1` Wrapper su `nmcli`: esecuzione comandi con timeout, parsing dell'output, traduzione dei fallimenti in `SYSTEM_TOOL_UNAVAILABLE` quando NetworkManager manca o non risponde. È la parte più fragile del progetto (il formato di `nmcli` cambia tra versioni) — dipende da `CORE-6`
- `NET-2` `GET /service/network/status`: `adapter` con priorità all'Ethernet quando entrambe sono attive, `state: "disconnected"` esplicito quando non c'è connessione, `signalInfo` solo su WiFi, elenco `interfaces` sempre presente — dipende da `NET-1`
- `NET-3` `GET /service/network/wifi/networks` e `POST /service/network/wifi/rescan` — dipende da `NET-1`
- `NET-4` `POST /service/network/wifi/connect` come job: riattiva l'autoconnect sulla rete scelta, distingue gli esiti `WIFI_AUTH_FAILED`, `WIFI_NETWORK_NOT_FOUND`, `WIFI_TIMEOUT`. Attenzione: l'IP della macchina cambia durante l'operazione — dipende da `CORE-5`, `NET-1`
- `NET-5` `POST /service/network/wifi/disconnect` come job: abbassa la connessione **e** spegne l'autoconnect, altrimenti NetworkManager si riconnette da solo dopo pochi secondi — dipende da `NET-4`
- `NET-6` `GET /service/network/wifi/saved` e `DELETE /service/network/wifi/saved/{ssid}` (`404` se la rete non è salvata) — dipende da `NET-1`
- `NET-7` `GET /service/network/ethernet/status` con `cableConnected` e `addressing` (`dhcp`/`static`), che lo stato unificato non dà — dipende da `NET-1`

## TZ — Fuso orario

- `TZ-1` Wrapper su `timedatectl` (lettura stato e `set-timezone`) con la relativa implementazione mock — dipende da `CORE-6`
- `TZ-2` `GET`/`POST /service/timezone`, con validazione dell'identificativo contro `/usr/share/zoneinfo/` e `400 INVALID_INPUT` se non esiste. `ntpSynchronized` è in sola lettura — dipende da `TZ-1`

## DEP — Deploy e aggiornamenti

- `DEP-1` Unit systemd `g2-service`: esecuzione come root, `uvicorn src.main:app --host 0.0.0.0 --port 8000`, `Restart=always`, `WantedBy=multi-user.target` — pronto
- `DEP-2` `Scripts/install.sh` idempotente (venv, dipendenze, unit systemd, `/etc/g2/`), invocabile sia da `69-G2-Service` di G2-OS sia da Moonraker a ogni aggiornamento — dipende da `DEP-1`
- `DEP-3` Deposito di `/etc/nginx/g2-locations.d/g2-service.conf` con la `location ^~ /service/` e reload di nginx, creando la directory se manca — dipende da `DEP-2`
- `DEP-4` Aggiunta del blocco `[update_manager G2-Service]` a `moonraker.conf`, **solo se assente** — dipende da `DEP-2`
- `DEP-5` Tollerare l'esecuzione dentro il chroot di build di G2-OS, dove `systemctl enable` funziona ma `start`/`restart` e il reload di nginx no: l'errore non deve far fallire la build dell'immagine — dipende da `DEP-2`
- `DEP-6` Verificare che il modulo [`69-G2-Service`](https://github.com/gingeradditive/G2-OS/blob/main/modules/generic/69-G2-Service) di G2-OS funzioni ancora con il nuovo `install.sh`. Nota: il repository è pubblico, quindi la logica `GITHUB_TOKEN`/SSH di quel modulo è inutilizzata e può essere semplificata — dipende da `DEP-2`

## DEV — Sviluppo locale e qualità

- `DEV-1` `rundev.sh`: venv locale, `uvicorn --reload`, mock automatico fuori da Linux, nessun privilegio richiesto — pronto
- `DEV-2` Implementazioni mock con dati verosimili (reti con segnali diversi, protette e aperte) e scenari di fallimento selezionabili con `G2_SERVICE_MOCK_SCENARIO`: password sbagliata, nessuna rete, NetworkManager assente — dipende da `CORE-6`
- `DEV-3` Test `pytest` mirati dove il codice è fragile: parsing dell'output `nmcli` (SSID con caratteri strani, campi vuoti, formati diversi) e contratto degli endpoint tramite il livello mock — dipende da `NET-3`, `DEV-2`
- `DEV-4` Configurare `ruff` per lint e formattazione; nessuna soglia di copertura, nessun `mypy` obbligatorio — pronto

## INT — Verifica

- `INT-1` Provare su Raspberry Pi reale il ciclo WiFi completo: scansione, connessione a una rete vera, cambio di IP, recupero dell'esito del job dal nuovo indirizzo, disconnessione senza riconnessione automatica — dipende da `NET-5`, `DEP-3`
- `INT-2` Verificare che i file scritti sotto `printer_data` restino modificabili da Moonraker (che gira come `pi`, mentre il servizio è root): è l'errore più facile da introdurre e si manifesta solo sulla macchina vera — dipende da `DEP-2`
- `INT-3` Verificare l'integrazione con GingerView aggiornato ai nuovi path (`NET-2`…`NET-5` nel suo TODO), passando da nginx e non in diretta — dipende da `INT-1`

---

# Parte 2 — Implementazioni future

Progettate e decise, ma **da non iniziare** senza una richiesta esplicita. La parte 1 deve
essere finita e verificata prima.

## FAC — Seriale di fabbrica

- `FAC-1` `GET`/`POST /service/factory/serial` con persistenza in `/etc/g2/serial`. Validazione solo di sicurezza (`[A-Za-z0-9._-]`, non vuoto) per impedire path traversal: l'esistenza su `G2-Printers` non si verifica in scrittura, perché al setup di fabbrica la rete può non esserci — dipende da `CORE-4`
- `FAC-2` Impostare il seriale fa partire subito una sincronizzazione, anche quando il seriale viene *corretto* su una macchina già configurata — dipende da `FAC-1`, `CFG-4`

## CFG — Configurazioni da G2-Printers

- `CFG-1` **Prerequisito fuori da questo repository**: creare `gingeradditive/G2-Printers`, pubblico, con una cartella per seriale e `main.cfg` come punto di ingresso. Oggi non esiste — pronto
- `CFG-2` Client dell'API contents di GitHub: lettura degli `sha` dei blob senza scaricare i contenuti, confronto con gli sha applicati salvati in `/etc/g2/config-version`, digest riassuntivo per `localVersion`/`remoteVersion` — dipende da `CORE-6`
- `CFG-3` `GET /service/config/status` (ultimo confronto noto, nessuna chiamata a GitHub) e `POST /service/config/check` (forza il confronto), con un limite di un check manuale al minuto per non consumare le 60 richieste/ora consentite senza autenticazione — dipende da `CFG-2`
- `CFG-4` `POST /service/config/sync` come job: scarica i file, riscrive `G2-Configs/` **come mirror** (cancellando ciò che non è più nel repository), riporta i permessi a `pi:pi`, salva i nuovi sha — dipende da `CFG-2`, `CORE-5`
- `CFG-5` Generare `printer.cfg` **solo se manca**, con il solo `[include G2-Configs/main.cfg]`, e non toccarlo mai più: è lì che Klipper scrive il blocco `SAVE_CONFIG` con la taratura dell'esemplare — dipende da `CFG-4`
- `CFG-6` Symlink `~/printer_data/config/moonraker.conf` → `G2-Configs/moonraker.conf`, più il controllo che il blocco `[update_manager G2-Service]` sia presente dopo ogni sync: se manca va segnalato nel log e in `updateManagerOk` di `config/status`, senza reinserirlo di nascosto — dipende da `CFG-4`
- `CFG-7` Riavvio di Kalico tramite l'API di Moonraker (`POST /printer/firmware_restart`) e non con `systemctl`, più il riavvio di Moonraker quando è cambiato `moonraker.conf`. Una stampa in corso non viene protetta: è una scelta esplicita — dipende da `CFG-4`
- `CFG-8` Sincronizzazione automatica all'avvio quando un seriale è configurato: parte **in background**, l'API resta subito disponibile, e ritenta 6 volte a 10 secondi di distanza prima di rinunciare in silenzio (al boot la rete non c'è ancora) — dipende da `CFG-4`, `FAC-1`
- `CFG-9` Esiti di fallimento dei job di configurazione: `CONFIG_SERIAL_NOT_SET`, `CONFIG_SERIAL_NOT_FOUND` (cartella assente nel repository), `CONFIG_DOWNLOAD_FAILED`, `CONFIG_RESTART_FAILED` — dipende da `CFG-4`

## AP — Onboarding di rete via Access Point

- `AP-1` Definire il comportamento con **un solo adattatore**: `wlan0` non può fare Access Point e client insieme, quindi passare in modalità AP significa staccarsi da ogni rete, e la scansione mentre l'AP è attivo va verificata sul campo. Da chiarire prima di scrivere codice → da decidere
- `AP-2` Apertura automatica dell'AP all'avvio quando nessuna rete salvata è raggiungibile e non c'è Ethernet, e chiusura una volta completata la configurazione — dipende da `AP-1`
- `AP-3` Campo `apActive` su `/service/network/status`, così GingerView sa di dover mostrare il wizard invece della pagina di rete normale — dipende da `AP-2`

## Estensioni valutate ma non pianificate

Non sono task: sono cose che abbiamo deciso di **non** fare ora, annotate perché non vengano
riproposte come dimenticanze.

- IP statico su Ethernet (`POST /service/network/ethernet/config`) — si aggiungerà se servirà.
- Impostazione manuale dell'ora e controllo di NTP — su Raspberry Pi OS la sincronizzazione è
  attiva di default e appena c'è rete l'ora si corregge da sola.
- Versionamento delle API nell'URL (`/service/v1/…`) — sovrastruttura finché l'unico client è
  GingerView, aggiornato insieme al servizio sulla stessa macchina.
- Rollback automatico di una configurazione che manda Kalico in errore — scelta esplicita: la
  macchina resta ferma e il problema si corregge pubblicando un fix.
