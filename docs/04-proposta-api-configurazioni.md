# 04 — Proposta API: Configurazioni stampante (G2-Printers)

> **Futuro, non in questa iterazione** (vedi [01 — Panoramica](01-panoramica.md#ambito-scope)).
> Questa è documentazione preparatoria: il design può cambiare quando si deciderà di
> affrontarlo davvero. A differenza di [03](03-proposta-api-rete-timezone.md), gli endpoint
> qui sotto **non sono ancora approvati** — restano una proposta di partenza. Domande a cui
> serve una risposta prima di poter implementare sono in [Q&A.md](Q&A.md) (Q4-Q7).

## Contesto

Le configurazioni Klipper/Kalico di ogni stampante (tutto ciò che oggi vive in
`printer_data/config/*`: `printer.cfg`, macro, ecc.) verranno **versionate in un repository
GitHub dedicato**, `G2-Printers`, con una cartella per stampante:

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

**Dove viene persistito il seriale sul Raspberry Pi, e quanto deve sopravvivere** (a un
riavvio? a un aggiornamento software? a un riflash della SD?) è una domanda aperta — **Q4** in
[Q&A.md](Q&A.md).

## 2. Sincronizzazione configurazione

| Metodo | Path | Richiesta | Risposta (sintesi) |
|---|---|---|---|
| GET | `/api/config/status` | — | `{ serial, localVersion, remoteVersion, updateAvailable, lastCheckedAt, lastSyncedAt }` — usa l'ultimo check noto, nessuna chiamata verso GitHub |
| POST | `/api/config/check` | — | Stesso shape di `status`, ma forza un fetch verso GitHub prima di rispondere |
| POST | `/api/config/sync` | — | `{ success, previousVersion, newVersion, filesChanged, restarted, message }` — scarica, applica, riavvia Klipper. È lo stesso percorso eseguito automaticamente a ogni avvio |

`localVersion`/`remoteVersion` presuppongono un modo per stabilire "cosa è più nuovo": se sia
il commit Git più recente che tocca la cartella della stampante, o un numero di versione
scritto a mano in un manifest per-stampante, è una domanda aperta — **Q6** in
[Q&A.md](Q&A.md).

Se `serial` non è ancora configurato (vedi punto 1), questi endpoint rispondono con uno stato
che lo segnala esplicitamente (niente da sincronizzare senza un'identità).

## 3. Comportamento all'avvio

All'avvio, se un seriale è configurato, G2-Service esegue automaticamente l'equivalente di
`POST /api/config/sync`: confronta, e se necessario scarica e applica, poi riavvia Klipper.
Questo succede **prima** che l'utente possa interagire con l'interfaccia, quindi non richiede
un endpoint dedicato — è comportamento interno, non API.

Cosa succede se il download fallisce (rete non disponibile al boot) o se i nuovi file
mandano in errore Klipper è una domanda aperta — **Q7** in [Q&A.md](Q&A.md): senza un
meccanismo di rollback, una config online rotta blocca la macchina finché non interviene
qualcuno manualmente.

## 4. Domande aperte

Prima di poter implementare questa parte servono risposte a **Q4-Q7** in
[Q&A.md](Q&A.md): dove persistere il seriale in modo duraturo, se `G2-Printers` è pubblico o
privato (e come G2-Service si autentica verso GitHub se privato), come si definisce "più
nuovo", e se serve un rollback automatico in caso di config rotta.
