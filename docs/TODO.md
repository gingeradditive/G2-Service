# TODO

Solo le cose da fare. Quando un task è completato viene **rimosso** da qui: quello che è già
stato fatto si legge nella documentazione (`01`–`05`), non in questo file.

**Codici.** Ogni task ha un codice `AREA-n` con cui puoi farvi riferimento rapidamente
("fai DEV-1", "INT-3 è bloccato"). I codici sono **stabili e non vengono mai riusati**:
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

**Stato di partenza.** Sono in piedi la struttura trasversale (prefisso `/service`, modello
degli errori, job asincroni, selezione reale/mock) e **tutti gli endpoint di
[03](03-proposta-api-rete-timezone.md)** — health, rete, fuso orario — ognuno con il proprio
mock: si legge in [02](02-architettura.md#organizzazione-del-codice). Tutto ciò che segue è da
scrivere. I codici `CORE-1`…`CORE-7`, `NET-1`…`NET-7`, `TZ-1`…`TZ-2` e `DEP-1`…`DEP-6` sono
stati consumati: i nuovi task di quelle aree partirebbero da `CORE-8`, `NET-8`, `TZ-3` e
`DEP-8`.

---

# Parte 1 — Implementazione corrente

Copre lo scope attuale: rete, fuso orario, e tutto ciò che serve per far girare e aggiornare il
servizio su una macchina vera.

**Ordine consigliato.** API e deploy ci sono: quello che resta è `INT`, cioè accendere una
macchina vera. È lì che si scopre se il giro WiFi funziona sul ferro e se il formato di
`nmcli` è quello che ci aspettiamo — cose che il mock, per costruzione, non può dire. `DEV-1`
conviene anticiparlo: senza `rundev.sh` si sviluppa scomodi.

## DEP — Deploy e aggiornamenti

- `DEP-7` Ripulire il modulo [`69-G2-Service`](https://github.com/gingeradditive/G2-OS/blob/develop/modules/generic/69-G2-Service) di G2-OS: togliere la logica `GITHUB_TOKEN`/SSH (codice morto, il repository è pubblico) e `python3-flask` dalle `DEPS` (residuo dell'implementazione precedente). **Sta in un altro repository** e non blocca niente: `install.sh` è già verificato contro il modulo così com'è — pronto

## DEV — Sviluppo locale e qualità

- `DEV-1` `rundev.sh`: venv locale, `uvicorn --reload`, mock automatico fuori da Linux, nessun privilegio richiesto — pronto
- `DEV-2` Implementazioni mock con dati verosimili (reti con segnali diversi, protette e aperte) e scenari di fallimento selezionabili con `G2_SERVICE_MOCK_SCENARIO`: password sbagliata, nessuna rete, NetworkManager assente — pronto
- `DEV-3` Test `pytest` mirati dove il codice è fragile: parsing dell'output `nmcli` (SSID con caratteri strani, campi vuoti, formati diversi) e contratto degli endpoint tramite il livello mock. Le funzioni di parsing sono già pure e senza dipendenze, in `services/network/nmcli.py` — dipende da `DEV-2`
- `DEV-4` Configurare `ruff` per lint e formattazione; nessuna soglia di copertura, nessun `mypy` obbligatorio — pronto

## INT — Verifica

- `INT-1` Provare su Raspberry Pi reale il ciclo WiFi completo: scansione, connessione a una rete vera, cambio di IP, recupero dell'esito del job dal nuovo indirizzo, disconnessione senza riconnessione automatica. Da guardare con attenzione: il formato di `nmcli` della macchina vera e la classificazione degli esiti di `connect`, verificati finora solo su output finto — pronto
- `INT-2` Verificare che i file scritti sotto `printer_data` restino modificabili da Moonraker (che gira come `pi`, mentre il servizio è root): è l'errore più facile da introdurre e si manifesta solo sulla macchina vera. Da controllare anche che il venv resti di `pi`, o l'update_manager non riesce più ad aggiornare le dipendenze — pronto
- `INT-3` Verificare l'integrazione con GingerView aggiornato ai nuovi path — sono i task `NET-2`…`NET-5` del TODO **di GingerView**, da non confondere con i codici di questo file — passando da nginx e non in diretta — dipende da `INT-1`

---

# Parte 2 — Implementazioni future

Progettate e decise, ma **da non iniziare** senza una richiesta esplicita. La parte 1 deve
essere finita e verificata prima.

## FAC — Seriale di fabbrica

- `FAC-1` `GET`/`POST /service/factory/serial` con persistenza in `/etc/g2/serial`. Validazione solo di sicurezza (`[A-Za-z0-9._-]`, non vuoto) per impedire path traversal: l'esistenza su `G2-Printers` non si verifica in scrittura, perché al setup di fabbrica la rete può non esserci — pronto
- `FAC-2` Impostare il seriale fa partire subito una sincronizzazione, anche quando il seriale viene *corretto* su una macchina già configurata — dipende da `FAC-1`, `CFG-4`

## CFG — Configurazioni da G2-Printers

- `CFG-1` **Prerequisito fuori da questo repository**: creare `gingeradditive/G2-Printers`, pubblico, con una cartella per seriale e `main.cfg` come punto di ingresso. Oggi non esiste — pronto
- `CFG-2` Client dell'API contents di GitHub: lettura degli `sha` dei blob senza scaricare i contenuti, confronto con gli sha applicati salvati in `/etc/g2/config-version`, digest riassuntivo per `localVersion`/`remoteVersion` — pronto
- `CFG-3` `GET /service/config/status` (ultimo confronto noto, nessuna chiamata a GitHub) e `POST /service/config/check` (forza il confronto), con un limite di un check manuale al minuto per non consumare le 60 richieste/ora consentite senza autenticazione — dipende da `CFG-2`
- `CFG-4` `POST /service/config/sync` come job: scarica i file, riscrive `G2-Configs/` **come mirror** (cancellando ciò che non è più nel repository), riporta i permessi a `pi:pi`, salva i nuovi sha — dipende da `CFG-2`
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
