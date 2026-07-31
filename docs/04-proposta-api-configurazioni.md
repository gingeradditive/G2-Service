# 04 — Proposta API: Configurazioni stampante (G2-Printers)

> **Design deciso, ma futuro**: non implementare senza una richiesta esplicita separata (vedi
> [01 — Panoramica](01-panoramica.md#ambito-scope)) — questo file resta documentazione, non un
> via libera a scrivere codice.

## Contesto

Le configurazioni Klipper/Kalico di ogni stampante (tutto ciò che oggi vive in
`printer_data/config/*`: `printer.cfg`, macro, ecc.) verranno **versionate in un repository
GitHub dedicato**, `G2-Printers` (**pubblico** — nessuna autenticazione verso GitHub necessaria
per leggerlo), con una cartella per stampante:

```
G2-Printers/
├── G2-0001-26/
│   └── printer.cfg
├── G2-0002-26/
│   └── printer.cfg
└── ...
```

Ogni stampante fisica è identificata da un **seriale** (es. `G2-0001-26`), che corrisponde al
nome della sua cartella in `G2-Printers`. Il seriale si imposta una volta, in fabbrica,
tramite un **menu segreto di factory configuration**: l'interfaccia è in GingerView, ma la
lettura/scrittura effettiva passa da un'API di G2-Service (che gira con i privilegi per
scrivere sul filesystem dell'host — stesso principio già stabilito in
[01 — Panoramica](01-panoramica.md#cosè-g2-service)).

Una volta che una stampante conosce il proprio seriale, G2-Service diventa responsabile di
tenere allineata la configurazione locale a quella pubblicata su `G2-Printers/<seriale>/`:
**a ogni avvio** confronta i file online con quelli locali, e se online sono più recenti li
scarica, li applica, e riavvia Klipper (e tutto ciò che serve perché i nuovi file abbiano
effetto). Deve inoltre esistere una via per forzare/controllare questo processo manualmente,
non solo al boot.

## 1. Seriale di fabbrica

| Metodo | Path | Richiesta | Risposta (sintesi) |
|---|---|---|---|
| GET | `/api/factory/serial` | — | `{ serial, configuredAt }` — `serial: null` se non ancora configurato |
| POST | `/api/factory/serial` | `{ serial }` | Stesso shape, `configuredAt` aggiornato |

`GET` con `serial: null` è anche il modo in cui GingerView capisce che la macchina è
"vergine" (non ha ancora un'identità) — utile per eventuali flussi guidati futuri, oltre al
menu segreto in sé.

Nessun controllo speciale lato server oltre alla validazione del formato: coerente con il
resto del progetto, che gira senza autenticazione (vedi
[03 — Decisioni prese](03-proposta-api-rete-timezone.md#decisioni-prese)) — la protezione
pratica è che il menu in GingerView è nascosto, non che l'API sia bloccata.

**Persistenza**: file semplice, `/etc/g2/serial`. Non deve sopravvivere a un riflash della SD —
in quel caso il seriale va reimpostato a mano dal form segreto (il cliente/tecnico lo fa di
nuovo, non serve un meccanismo di recupero automatico).

## 2. Sincronizzazione configurazione

| Metodo | Path | Richiesta | Risposta (sintesi) |
|---|---|---|---|
| GET | `/api/config/status` | — | `{ serial, localVersion, remoteVersion, updateAvailable, lastCheckedAt, lastSyncedAt }` — usa l'ultimo check noto, nessuna chiamata verso GitHub |
| POST | `/api/config/check` | — | Stesso shape di `status`, ma forza un fetch verso GitHub prima di rispondere |
| POST | `/api/config/sync` | — | `{ success, previousVersion, newVersion, filesChanged, restarted, message }` — scarica, applica, riavvia Klipper. È lo stesso percorso eseguito automaticamente a ogni avvio |

**Come si determina "più nuovo"**: l'hash del blob Git di ogni file, non un numero di versione
scritto a mano. L'API GitHub (`GET /repos/gingeradditive/G2-Printers/contents/<seriale>`)
restituisce, per ogni file nella cartella della stampante, il suo `sha` senza dover scaricare
il contenuto. G2-Service salva localmente l'ultimo `sha` applicato per ciascun file (es. in
`/etc/g2/config-version`); a ogni check confronta gli sha remoti con quelli salvati — se anche
uno solo differisce, `updateAvailable: true`. `localVersion`/`remoteVersion` nella tabella sopra
sono un riassunto di questo confronto (es. un digest calcolato sull'insieme `path:sha`), non un
singolo commit dell'intero repository. Il contenuto vero e proprio si scarica solo in fase di
`sync`, non durante un semplice `check`.

Se `serial` non è ancora configurato (vedi punto 1), questi endpoint rispondono con uno stato
che lo segnala esplicitamente (niente da sincronizzare senza un'identità).

## 3. Comportamento all'avvio

All'avvio, se un seriale è configurato, G2-Service esegue automaticamente l'equivalente di
`POST /api/config/sync`: confronta, e se necessario scarica e applica, poi riavvia Klipper.
Questo succede **prima** che l'utente possa interagire con l'interfaccia, quindi non richiede
un endpoint dedicato — è comportamento interno, non API.

**Nessun rollback automatico** (deciso): se una nuova configurazione manda in errore Klipper,
la macchina resta ferma finché qualcuno non corregge il problema pubblicando un fix su
`G2-Printers` — scelta esplicita, per non rischiare che un rollback nasconda il problema. Il
pulsante "controlla aggiornamenti" previsto in GingerView (chiama `POST /api/config/check` e
`POST /api/config/sync`, già in tabella al punto 2) è anche lo strumento per forzare un nuovo
tentativo dopo che il fix è stato pubblicato.
