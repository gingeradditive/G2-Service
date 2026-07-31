# Q&A

Domande aperte che servono per procedere con lo sviluppo. Rispondi sotto ogni `A:`, anche in
momenti diversi.

**Come funziona il file.** Quando una domanda riceve risposta, viene rimossa da qui e la
decisione finisce nella documentazione (`01`–`05`). L'obiettivo è arrivare ad avere questo
file **vuoto**.

La numerazione **non** viene mai riusata: le nuove domande partono da dove finiscono le
vecchie, così i rimandi `Qn` nella documentazione restano validi nel tempo.

Le domande marcate **[BLOCCANTE]** vanno risolte prima di scrivere codice: senza una risposta
dovrei inventare una convenzione che poi si propaga ovunque.

---

## Integrazione con nginx e GingerView

**Q8 [BLOCCANTE]: il prefisso `/api/` collide con Moonraker. Teniamo `/api/network/` con
eccezioni multiple, o spostiamo tutto G2-Service sotto un prefisso dedicato?**
Contesto: in produzione GingerView chiama **same-origin** (`apiBaseUrl` è la stringa vuota,
vedi `buildNetworkConfig()` in `src/lib/services/config.ts`), quindi ogni richiesta passa da
nginx. La configurazione nginx la scrive GingerView (`script/install.sh`) e contiene:

```nginx
location ^~ /api/wifi/ { proxy_pass http://.../; }             # servizio di rete
location ~ ^/(printer|api|access|machine|server)/ { ... }       # tutto il resto → Moonraker
```

Cioè **`/api/` appartiene a Moonraker** (è il suo layer OctoPrint-compatibile, che gli slicer
interrogano) e il servizio di rete esiste solo grazie a un'eccezione `^~` puntuale. Con il
naming deciso in [03](03-proposta-api-rete-timezone.md)/[04](04-proposta-api-configurazioni.md)
servirebbero **quattro** eccezioni separate (`/api/network/`, `/api/timezone`, `/api/factory/`,
`/api/config/`) — e una nuova ogni volta che aggiungiamo un namespace, ognuna da ricordarsi di
aggiungere in un altro repository. Un `/api/config/` per giunta è pericolosamente vicino a
namespace che Moonraker potrebbe usare in futuro.
Alternativa: **un unico prefisso tutto nostro**, es. `/g2/network/status`, `/g2/timezone`,
`/g2/factory/serial`, `/g2/config/sync` → una sola regola nginx (`location ^~ /g2/`) valida per
sempre, zero rischio di collisione. Costo: i path cambiano rispetto a quanto già scritto in 03
e 04 (che comunque non sono implementati) e GingerView va aggiornato (cosa già prevista).
A:

**Q9: su quale porta ascolta G2-Service, e su quale indirizzo?**
Contesto: [05](05-deploy-e-sviluppo.md) ipotizza `8080`, ma GingerView oggi usa **8000**
(`NETWORK_API_PORT="${NETWORK_API_PORT:-8000}"` in `script/install.sh`) — il vecchio G2-Service
era passato da 8000 a 8080 e i due repository non sono mai stati riallineati. Va scelto un
numero e allineato in entrambi. Inoltre: il servizio deve ascoltare su `127.0.0.1` (raggiungibile
**solo** via nginx — più sicuro, nessuna porta esposta sulla rete) o su `0.0.0.0` (raggiungibile
anche direttamente, comodo per debug e per GingerView in sviluppo che punta alla stampante
reale)? Il vecchio codice usava `0.0.0.0` deliberatamente.
A:

**Q10: chi possiede la configurazione nginx delle rotte di G2-Service?**
Contesto: oggi il site nginx è scritto interamente da GingerView (`script/install.sh`), inclusa
la `location` del servizio di rete. Significa che un cambio di path in G2-Service richiede una
modifica in un altro repository, e che chi installa G2-Service senza GingerView non ha proxy.
Alternativa: G2-Service installa un proprio snippet in `/etc/nginx/conf.d/` (o
`sites-available`), autonomo. Va bene l'accoppiamento attuale o preferisci l'autonomia?
A:

## Hardware di rete

**Q11 [BLOCCANTE]: quante interfacce WiFi ha la G2, e come si chiamano?**
Contesto: il codice deve sapere su quale interfaccia operare, e non posso dedurlo. Il vecchio
G2-Service (rimosso) assumeva **due** adattatori: `wlan1` per la connessione client
(`self.wifi_interface = "wlan1"`, con un `_validate_wlan1()` che falliva tutto se assente) e
`wlan0` riservato all'Access Point, addirittura sottratto a NetworkManager in modo persistente
(`/etc/NetworkManager/conf.d/unmanaged-wlan0.conf`). Il Raspberry Pi 4 ha un solo WiFi
integrato (`wlan0`), quindi quel design presupponeva **una chiavetta USB aggiuntiva**. Serve
sapere: (a) la G2 monta un secondo adattatore WiFi USB o solo quello integrato del Pi? (b) se
solo quello integrato, l'Access Point futuro dovrà cambiare modalità sulla stessa interfaccia
(AP e client mutuamente esclusivi, niente scansione mentre l'AP è attivo); (c) i nomi vanno
scritti fissi nel codice o rilevati a runtime (più robusto se l'hardware cambia)?
A:

**Q12: come si chiama l'interfaccia Ethernet, e va rilevata o fissata?**
Contesto: serve per `/api/network/ethernet/status`. Su Raspberry Pi OS è tipicamente `eth0`,
ma i "predictable interface names" possono produrre nomi diversi (`enxAABBCCDDEEFF`). Fisso
`eth0` (semplice, si rompe se cambia) o rilevamento automatico della prima interfaccia
cablata (più robusto)?
A:

## Semantica delle API

**Q13 [BLOCCANTE]: le operazioni lunghe sono sincrone o asincrone?**
Contesto: connettersi a una rete WiFi richiede facilmente 10–30 secondi (il vecchio codice
faceva `sleep(3)` e poi verificava, con più tentativi in cascata); una sincronizzazione
configurazioni con riavvio di Klipper può richiedere di più. nginx ha un `proxy_read_timeout`
di 60s di default — GingerView lo alza a 3600 **solo** per le rotte Moonraker, non per il
servizio di rete. Due modelli: **(a) sincrono** — la POST resta appesa finché l'operazione
finisce, semplice da consumare ma rischia timeout e non dà feedback di avanzamento; **(b)
asincrono** — la POST accetta e risponde subito con un id, il client fa polling su un endpoint
di stato (o si aggancia a un websocket). Il secondo è più lavoro ma è l'unico che regge
operazioni davvero lunghe e permette a GingerView di mostrare un progresso. Quale adottiamo, e
vale per tutte le operazioni lunghe o solo per la sync configurazioni?
A:

**Q14 [BLOCCANTE]: qual è il modello degli errori?**
Contesto: il vecchio codice era incoerente — `connect_to_network()` restituiva **HTTP 200** con
`{"success": false, "status": "error"}` per un fallimento di connessione, mentre altri errori
diventavano `HTTPException(500)`. GingerView si è adattato a questa incoerenza. Va deciso una
volta: quali situazioni sono errori HTTP (4xx/5xx) e quali sono 200 con esito nel corpo. Casi
concreti da classificare: password errata, SSID inesistente, `nmcli` non installato/non
raggiungibile, timeout di connessione, timezone non valida, seriale non ancora configurato.
La mia proposta: 4xx/5xx per *errori della richiesta o del servizio* (input non valido, tool di
sistema assente), 200 con `success:false` per *esiti negativi previsti dell'operazione*
(password sbagliata, rete non raggiungibile) — ma dimmi tu.
A:

**Q15: `/wifi/disconnect` deve solo disconnettere o anche impedire la riconnessione
automatica?**
Contesto: NetworkManager per default riconnette da solo alla rete salvata, anche subito dopo un
`connection down`. Se "disconnect" significa solo abbassare la connessione, l'utente potrebbe
vedere la macchina riconnettersi da sola dopo pochi secondi e pensare che il comando non abbia
funzionato. L'alternativa è disattivare anche l'autoconnect della connessione (che però poi va
riattivato da qualche parte). Quale comportamento vuoi?
A:

**Q16: cosa risponde `/api/network/status` nei casi limite?**
Contesto: (a) nessuna connessione attiva — `adapter` con campi vuoti/`null`, o un `state`
esplicito tipo `"disconnected"`? (b) **entrambe** le interfacce attive (cavo + WiFi
contemporaneamente, scenario realistico in officina): quale delle due riporta `adapter`?
Propongo priorità all'Ethernet (è la connessione che il sistema userebbe di default), ma è una
convenzione che GingerView mostrerà all'utente, quindi la decidi tu. (c) Serve un elenco di
*tutte* le interfacce invece di una sola "attiva"?
A:

**Q17: `POST /api/timezone` tocca anche NTP?**
Contesto: la risposta include `ntpSynchronized`, che oggi è pura lettura di stato. Serve anche
poterlo **impostare** (abilitare/disabilitare la sincronizzazione oraria, o impostare l'ora a
mano quando la macchina è offline e l'orologio del Pi è sbagliato — il Pi non ha RTC, quindi
senza rete l'ora è sempre sbagliata)? Oppure `ntpSynchronized` resta in sola lettura?
A:

## Sincronizzazione configurazioni (doc 04)

**Q18 [BLOCCANTE]: `SAVE_CONFIG` di Klipper riscrive `printer.cfg` sulla macchina. Come
convive con un `printer.cfg` versionato che viene sovrascritto?**
Contesto: questo è il problema più serio del design di [04](04-proposta-api-configurazioni.md).
Klipper, quando l'utente esegue una calibrazione (`PID_CALIBRATE`, `Z_OFFSET_APPLY`,
`SHAPER_CALIBRATE`, ...) e poi `SAVE_CONFIG`, **scrive i risultati in fondo a `printer.cfg`**
in un blocco `#*# <---------------------- SAVE_CONFIG ---------------------->`. Se G2-Service
sovrascrive `printer.cfg` con la versione del repository, **tutta la calibrazione della singola
macchina viene persa** (z-offset, PID, resonance) — e sono valori specifici di quell'esemplare
fisico, non replicabili dal repository. Opzioni: (a) preservare e riapplicare il blocco
`SAVE_CONFIG` locale dopo ogni sync; (b) non versionare `printer.cfg` ma solo file inclusi da
esso, tenendo `printer.cfg` locale come "guscio" con gli `[include]` e il blocco SAVE_CONFIG;
(c) far sì che il repository contenga anche i valori calibrati, aggiornandolo dalla macchina
(sync bidirezionale — molto più complesso). Come vuoi gestirlo?
A:

**Q19 [BLOCCANTE]: cosa contiene esattamente `G2-Printers/<seriale>/`, e `moonraker.conf` ne
fa parte?**
Contesto: il precedente `G1-Configs` (repo pubblico esistente) conteneva, oltre alle config
Klipper, anche **`moonraker.conf`** e `mainsail.cfg`. Se `G2-Printers` includesse
`moonraker.conf`, sincronizzarlo **cancellerebbe il blocco `[update_manager G2-Service]`** che
`install.sh` aggiunge (vedi [05](05-deploy-e-sviluppo.md)) e anche quelli di
Kalico/GingerView/KAMP scritti da G2-OS — disattivando di fatto gli aggiornamenti della
macchina. Serve un elenco esplicito di cosa è sotto sync: solo `*.cfg` di Klipper? anche
macro? `moonraker.conf` va escluso o gestito con un merge?
A:

**Q20 [BLOCCANTE]: la sync è un mirror (cancella ciò che non è nel repo) o un merge (sovrascrive
solo i file presenti nel repo)?**
Contesto: sulla macchina esistono file che il repository non conosce: `KAMP_Settings.cfg`
copiato da G2-OS, eventuali file creati dall'utente da GingerView, file di variabili salvate.
Un mirror li cancellerebbe; un merge lascerebbe residui di configurazioni vecchie che nessuno
rimuove più. Quale semantica vuoi, e c'è una lista di file/percorsi da proteggere sempre?
A:

**Q21: dove vengono scritti i file scaricati?**
Contesto: direttamente in `~/printer_data/config/` (semplice, ma mescola file gestiti e file
utente — vedi Q20), oppure in una sottocartella dedicata tipo
`~/printer_data/config/G2-Configs/` inclusa da `printer.cfg` con degli `[include]` (separazione
netta tra "gestito dal repository" e "locale", e risolverebbe in parte anche Q18)? Il vecchio
install.sh creava proprio un symlink `~/printer_data/config/G2-Configs`.
A:

**Q22 [BLOCCANTE]: come si riavvia Klipper dopo una sync?**
Contesto: [01](01-panoramica.md) stabilisce che G2-Service è indipendente da Moonraker, ma qui
serve un riavvio. Opzioni: (a) `systemctl restart kalico` direttamente — coerente con
l'indipendenza, ma Moonraker se lo trova riavviato sotto i piedi e potrebbe mostrare stati
incoerenti ai client; (b) chiamare l'API di Moonraker (`POST /printer/firmware_restart` o
`/machine/services/restart?service=kalico`) — Moonraker resta allineato e avvisa i client via
websocket, ma introduce una dipendenza da Moonraker che finora non c'era. C'è poi il caso in
cui una stampa è **in corso**: un riavvio la interromperebbe. La sync va rimandata? Rifiutata
con un errore? (Al boot il problema non si pone, ma con la sync manuale sì.)
A:

**Q23: che formato ha il seriale, e cosa succede se non esiste su G2-Printers?**
Contesto: l'esempio è `G2-0001-26`. Serve la regola per validarlo lato server (regex? `G2-`
fisso + progressivo + anno?) e il comportamento quando la cartella corrispondente **non esiste**
nel repository — seriale digitato male, o stampante non ancora registrata. Va rifiutato in
scrittura (verificando subito su GitHub, ma allora serve rete al momento del setup di fabbrica),
o accettato e segnalato solo al primo tentativo di sync?
A:

**Q24: la sync all'avvio è bloccante, e per quanto?**
Contesto: [04](04-proposta-api-configurazioni.md) dice che avviene "prima che l'utente possa
interagire". Ma se al boot la rete non c'è (caso normale: il WiFi si associa dopo qualche
secondo) o GitHub non risponde, quanto aspettiamo prima di rinunciare e avviare comunque? E il
servizio HTTP di G2-Service risponde già durante il tentativo, o parte solo dopo? Nota:
GitHub senza autenticazione limita a **60 richieste/ora per IP** — un check al boot e qualcuno
manuale stanno larghi, ma un polling automatico da GingerView no. Serve una frequenza massima
o una cache?
A:

**Q25: cambiare il seriale a macchina già configurata cosa comporta?**
Contesto: se un tecnico corregge il seriale dal menu di fabbrica, le configurazioni locali sono
quelle della stampante sbagliata. Va forzata una sync immediata? Vanno cancellate le config
precedenti? O è responsabilità dell'operatore lanciare la sync a mano?
A:

## Convenzioni di progetto

**Q26: come organizziamo il codice?**
Contesto: oggi c'è solo `src/main.py` con l'endpoint di health. Con rete, timezone e (poi)
configurazioni serve una struttura. La mia proposta: `src/main.py` (creazione app + inclusione
dei router), `src/routers/` (un modulo per area: `network.py`, `timezone.py`, ...),
`src/services/` (l'accesso vero a `nmcli`/`timedatectl`/GitHub, dove vive anche il mock),
`src/models/` (schemi Pydantic di richiesta/risposta). Ti va bene o preferisci un'altra
organizzazione?
A:

**Q27: con quali privilegi gira il servizio?**
Contesto: `nmcli` per modificare connessioni e `timedatectl set-timezone` richiedono privilegi.
Opzioni: (a) il servizio gira **come root** — tutto funziona, zero attrito, ma un'API senza
autenticazione esposta sulla rete gira con i massimi privilegi; (b) gira come utente `pi` e
invoca i singoli comandi con `sudo`, con una regola sudoers ristretta ai comandi necessari —
più sicuro, un po' più di lavoro. Il vecchio codice faceva un misto (servizio root *e* `sudo`
sparso nei comandi). Quale scegliamo?
A:

**Q28: che livello di test ti aspetti, e con quali strumenti?**
Contesto: quasi tutto il servizio è un wrapper su comandi Linux, quindi su Mac è testabile solo
con mock. Propongo `pytest` + `httpx` per i test degli endpoint, con i servizi di sistema
sostituiti dai mock (utile anche per il parsing dell'output `nmcli`, che è la parte più
fragile). Serve anche linting/formattazione automatica (`ruff`) e type checking (`mypy`)? Vuoi
una soglia di copertura o basta "i test passano"?
A:

**Q29: come deve comportarsi esattamente la modalità mock?**
Contesto: [05](05-deploy-e-sviluppo.md) fissa la variabile `G2_SERVICE_MOCK` ma non cosa
restituisce. Dati statici scritti nel codice, o un file di fixture modificabile a mano per
provare scenari diversi? Deve poter simulare i **fallimenti** (password sbagliata, nessuna rete
trovata, GitHub irraggiungibile) o basta il caso felice? Questo determina quanto è utile per
sviluppare GingerView contro un G2-Service finto.
A:

**Q30: le API vanno versionate?**
Contesto: es. `/api/v1/network/status` invece di `/api/network/status`. Dato che l'unico client
è GingerView e viene aggiornato insieme al servizio dalla stessa macchina, il versionamento è
probabilmente sovrastruttura — ma se in futuro GingerSlicer o altri strumenti dovessero parlare
con la stampante, cambiare un contratto pubblicato diventa un problema. Versioniamo da subito o
no?
A:

**Q31: cosa deve restituire `/health`, e serve un endpoint di versione?**
Contesto: oggi risponde `{"status": "ok"}`. Serve qualcosa di più — versione del servizio,
uptime, stato dei sottosistemi (`nmcli` disponibile, seriale configurato, ultima sync riuscita)
— per diagnosticare una macchina da remoto? È anche il posto naturale dove GingerView può
capire se G2-Service è presente e quale versione parla.
A:
