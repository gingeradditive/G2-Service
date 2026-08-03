# 04 — API: Configurazioni stampante (G2-Printers)

> Contratto **deciso**, non ancora implementato — e da non implementare senza una richiesta
> esplicita. Le convenzioni trasversali stanno in
> [02 — Architettura](02-architettura.md#convenzioni-comuni-a-tutte-le-api).

## Stato dei prerequisiti (verificato il 2026-07-31)

- **`gingeradditive/G2-Printers` non esiste ancora** — va creato prima di poter implementare
  qualsiasi cosa di questo capitolo.
- Il precedente è **`gingeradditive/G1-Configs`** (pubblico): contiene un *unico* set di
  configurazioni condiviso da tutte le G1, non una cartella per macchina. `G2-Printers`
  introduce quindi un modello nuovo, non un'evoluzione diretta di quello.
- `gingeradditive/G2-Service` è **pubblico** e il modulo `69-G2-Service` di G2-OS lo clona in
  anonimo: in nessun punto della catena serve un token.

## Contesto

Le configurazioni Klipper/Kalico di ogni stampante vengono versionate in un repository GitHub
**pubblico** dedicato, `G2-Printers` (nessuna autenticazione necessaria per leggerlo), con una
cartella per stampante:

```
G2-Printers/
├── G2-0001-26/
│   ├── main.cfg          punto di ingresso, include gli altri file
│   ├── macro.cfg
│   └── moonraker.conf
├── G2-0002-26/
└── ...
```

Ogni stampante fisica è identificata da un **seriale** (es. `G2-0001-26`), che corrisponde al
nome della sua cartella. Il seriale si imposta una volta, in fabbrica, da un **menu segreto**
in GingerView, che chiama le API del punto 1.

## 1. Seriale di fabbrica

| Metodo | Path | Richiesta | Risposta |
|---|---|---|---|
| GET | `/service/factory/serial` | — | `{ serial, configuredAt }` — `serial: null` se mai impostato |
| POST | `/service/factory/serial` | `{ serial }` | Stesso shape, `configuredAt` aggiornato |

**Persistenza**: file di testo `/etc/g2/serial`. Non deve sopravvivere a un riflash della SD:
in quel caso il seriale si reimposta a mano dal menu segreto.

**Validazione**: il seriale viene accettato e salvato **anche se non esiste** una cartella
corrispondente su `G2-Printers` — non si verifica su GitHub al momento della scrittura, perché
al setup di fabbrica la rete potrebbe non esserci. L'unico controllo è di sicurezza, non di
formato: la stringa deve essere non vuota e contenere solo `[A-Za-z0-9._-]`, così non può
contenere `/` o `..` e trasformarsi in una path traversal quando viene concatenata all'URL del
repository o a un percorso locale.

Un seriale inesistente su `G2-Printers` si scopre alla prima sincronizzazione, che fallisce con
`CONFIG_SERIAL_NOT_FOUND`. È il posto giusto per segnalarlo all'utente.

**Impostare il seriale fa partire subito una sincronizzazione** (vedi punto 3): è il momento in
cui la macchina acquisisce la propria identità, e le configurazioni presenti sono presumibilmente
quelle sbagliate. Vale anche quando il seriale viene *corretto* su una macchina già configurata.

Nessuna protezione particolare sull'endpoint: la protezione pratica è che il menu in GingerView
è nascosto, coerentemente con il fatto che tutto il servizio è senza autenticazione.

## 2. Dove finiscono i file

La separazione è la chiave di tutto il capitolo: **ciò che è gestito dal repository sta in una
cartella dedicata, ciò che appartiene alla singola macchina sta fuori.**

```
~/printer_data/config/
├── printer.cfg            LOCALE — generato se manca, mai sincronizzato
├── moonraker.conf         symlink → G2-Configs/moonraker.conf
├── KAMP_Settings.cfg      LOCALE — di G2-OS, mai toccato
└── G2-Configs/            GESTITA DAL REPOSITORY — mirror di G2-Printers/<seriale>/
    ├── main.cfg
    ├── macro.cfg
    └── moonraker.conf
```

### `printer.cfg` non è versionato

È il punto più delicato del design. Klipper, dopo una calibrazione (`PID_CALIBRATE`,
`Z_OFFSET_APPLY`, `SHAPER_CALIBRATE`, ...) e un `SAVE_CONFIG`, **riscrive `printer.cfg`**
aggiungendo in fondo un blocco `#*# <---------------------- SAVE_CONFIG ---------------------->`
con i valori misurati. Sono valori del singolo esemplare fisico: sovrascriverli con una copia
dal repository cancellerebbe la taratura della macchina, e nessuno potrebbe ricostruirla.

Perciò `printer.cfg` resta **locale e fuori dalla sincronizzazione**. G2-Service lo **genera solo
se manca**, con il minimo indispensabile:

```ini
[include G2-Configs/main.cfg]
```

Da lì in poi il file appartiene alla macchina: Klipper ci scrive il blocco `SAVE_CONFIG` e
nessuna sincronizzazione lo tocca più. Tutta la configurazione vera vive in `G2-Configs/`, dove
`main.cfg` fa da punto di ingresso e include il resto.

### `moonraker.conf` è del repository

Diversamente da `printer.cfg`, `moonraker.conf` **è** sotto sincronizzazione: viene scaricato in
`G2-Configs/` come gli altri, e `~/printer_data/config/moonraker.conf` è un **symlink** che punta
lì (Moonraker legge quel percorso esatto, quindi serve il collegamento).

⚠️ **Conseguenza da tenere presente.** `moonraker.conf` contiene i blocchi `[update_manager …]`
che permettono di aggiornare Kalico, GingerView e G2-Service stesso. Se la copia pubblicata su
`G2-Printers` li omette, **la macchina perde la capacità di aggiornarsi**. È un rischio accettato
consapevolmente: la copia nel repository deve sempre contenerli. G2-Service non li reinserisce di
nascosto — sarebbe un comportamento occulto che contraddice "il repository è la fonte di verità" —
ma **dopo ogni sync verifica che `[update_manager G2-Service]` sia presente e, se manca, lo
segnala** nel log e in `GET /service/config/status`. La situazione resta recuperabile da remoto:
basta pubblicare un `moonraker.conf` corretto, perché la sincronizzazione continua a funzionare
anche quando l'update manager è rotto.

### Mirror, ma solo dentro `G2-Configs/`

Dentro `G2-Configs/` la sincronizzazione è un **mirror**: i file che non sono più nel repository
vengono cancellati, così una configurazione ritirata sparisce davvero e non resta a sporcare la
macchina.

Fuori da `G2-Configs/` non viene toccato **nulla**: `printer.cfg`, `KAMP_Settings.cfg`, i file
creati dall'utente dall'editor di GingerView restano dove sono. È questa separazione a rendere
sicuro il mirror — non serve una lista di file protetti, perché l'unica cartella che
G2-Service riscrive è quella che possiede per intero.

I file scritti sotto `printer_data` vanno riportati a `pi:pi` dopo la scrittura: il servizio gira
come root, ma Moonraker gira come `pi` e deve poterli leggere e modificare (vedi
[02 — Privilegi](02-architettura.md#privilegi-ed-esecuzione)).

## 3. Sincronizzazione

| Metodo | Path | Richiesta | Risposta | Tipo |
|---|---|---|---|---|
| GET | `/service/config/status` | — | stato dell'ultimo confronto noto, nessuna chiamata a GitHub | sincrono |
| POST | `/service/config/check` | — | forza un confronto con GitHub e restituisce lo stato aggiornato | sincrono |
| POST | `/service/config/sync` | — | `202` + job | **asincrono** |

```json
// GET /service/config/status
{
  "serial": "G2-0001-26",
  "updateAvailable": true,
  "localVersion": "a1b2c3d4",
  "remoteVersion": "e5f6a7b8",
  "lastCheckedAt": "2026-07-31T10:00:00Z",
  "lastSyncedAt": "2026-07-30T18:12:00Z",
  "updateManagerOk": true
}
```

Se il seriale non è configurato, questi endpoint rispondono con `serial: null` e
`updateAvailable: false`; un `sync` in quella condizione fallisce con `CONFIG_SERIAL_NOT_SET`.

### Come si stabilisce cosa è "più nuovo"

Tramite l'**hash del blob Git di ogni file**, senza scaricarne il contenuto.
`GET /repos/gingeradditive/G2-Printers/contents/<seriale>` restituisce per ogni file il suo
`sha`. G2-Service tiene in `/etc/g2/config-version` gli sha applicati l'ultima volta; a ogni
check confronta i due insiemi e se anche uno solo differisce (o un file è comparso/sparito)
`updateAvailable` diventa `true`. `localVersion`/`remoteVersion` sono un digest calcolato
sull'insieme `path:sha`, comodo da mostrare, non un commit del repository.

Il contenuto vero si scarica **solo** durante `sync`, mai durante `check`.

### Applicazione e riavvio

Il job `config.sync` esegue in ordine: scarica i file, riscrive `G2-Configs/` come mirror,
genera `printer.cfg` se manca, aggiorna il symlink di `moonraker.conf`, sistema i permessi,
salva i nuovi sha, e infine **riavvia Kalico chiamando l'API di Moonraker**
(`POST /printer/firmware_restart`) invece di `systemctl`. Così Moonraker resta allineato e
avvisa i propri client via websocket, invece di trovarsi il firmware riavviato sotto i piedi.
Se anche `moonraker.conf` è cambiato, va riavviato pure Moonraker
(`POST /machine/services/restart?service=moonraker`).

È l'unico punto in cui G2-Service dipende da Moonraker (vedi
[02](02-architettura.md#g2-service-nello-stack-g2)).

**Una stampa in corso non viene protetta**: un `sync` manuale durante una stampa la interrompe.
È una scelta esplicita — il pulsante sta in un menu che si usa consapevolmente, e aggiungere
una logica di attesa complicherebbe il flusso per un caso raro. Al boot il problema non si pone.

### Nessun rollback automatico

Se una configurazione pubblicata è rotta e Kalico non riparte, la macchina resta ferma finché
qualcuno non pubblica un `G2-Printers` corretto. Scelta esplicita: un rollback nasconderebbe il
problema. Il pulsante di controllo aggiornamenti in GingerView (`check` + `sync`) è lo strumento
per ritentare dopo il fix.

## 4. Comportamento all'avvio

Se un seriale è configurato, all'avvio G2-Service esegue una sincronizzazione da solo.

L'API HTTP **è disponibile subito**: la sincronizzazione parte in background come un normale job,
non blocca l'avvio del servizio. Una macchina senza rete deve comunque rispondere — è proprio da
GingerView che l'utente andrà a configurare il WiFi.

Al boot la rete non c'è ancora (il WiFi si associa qualche secondo dopo), quindi il primo
tentativo viene ripetuto: **6 tentativi a 10 secondi di distanza**, cioè fino a circa un minuto
di attesa. Se dopo l'ultimo tentativo GitHub resta irraggiungibile si rinuncia in silenzio: la
macchina funziona con le configurazioni che ha già, e l'utente può forzare un `sync` a mano
quando la rete c'è.

**Limite di GitHub**: le API senza autenticazione ammettono 60 richieste/ora per IP. Un check al
boot e qualcuno manuale stanno larghissimi, ma un polling automatico da GingerView no. Per questo
non esiste nessun controllo periodico: si controlla al boot, quando si imposta il seriale, e
quando l'utente lo chiede. Un `check` manuale non può essere ripetuto più di una volta al minuto.
