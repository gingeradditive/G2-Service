# 03 — Proposta API: Rete e Timezone

> Elenca gli endpoint che G2-Service esporrà per rete (WiFi/Ethernet) e timezone. Naming e
> convenzioni sono **decisi** (vedi sotto); i singoli endpoint 🆕 restano da confermare se
> servono davvero prima di implementarli. Nessuno di questi endpoint esiste ancora nel codice
> (vedi [02 — Architettura](02-architettura.md#stato-attuale)). Domande ancora aperte, se ce ne
> sono, sono in [Q&A.md](Q&A.md).

## Decisioni prese

- **Prefisso `/api/network/`** per tutto ciò che riguarda la connettività, WiFi ed Ethernet
  incluse, con sotto-namespace `/api/network/wifi/*` per le operazioni specifiche del WiFi
  (scansione, connessione — non hanno equivalente su cavo). Lo stato generico vive alla radice
  (`/api/network/status`) perché copre entrambe le interfacce.
- **`camelCase` uniforme** su tutti gli endpoint, rete e timezone. Il vecchio contratto WiFi
  (mai implementato, solo cablato nel client GingerView) usava `snake_case`; si abbandona a
  favore di `camelCase`, coerente con il contratto timezone e più idiomatico per un'API JSON
  consumata da un client JS/TS.
- **GingerView andrà aggiornato di conseguenza** — questi path e questi nomi campo sono
  diversi da quelli oggi hardcoded in `network-api.ts`/`timezone.ts`. Non è un aggiornamento a
  costo zero lato client, è una scelta consapevole (vedi [01 — Panoramica](01-panoramica.md#chi-lo-consuma)).
- Nessuna autenticazione, coerente con Moonraker su G2-OS (che gira senza auth).
- Errori di validazione nel formato di default FastAPI: `{"detail": [{"loc", "msg", "type"}]}`.

## Legenda

- ✅ **Necessario** — copre una funzionalità che l'interfaccia di rete/timezone deve avere.
- 🆕 **Proposta aggiuntiva** — non richiesta da nessuna funzionalità nota oggi, da valutare
  prima di implementarla.
- 🔮 **Futuro, non ora** — parte del flusso di onboarding via Access Point (vedi punto 5),
  esplicitamente rimandato.

---

## 1. Stato di rete (unificato)

| Metodo | Path | Richiesta | Risposta (sintesi) | Stato |
|---|---|---|---|---|
| GET | `/api/network/status` | — | `{ adapter: { device, type, state, connection }, ip: { ipv4, ipv6, mac }, signalInfo? }` — `signalInfo` presente solo se `adapter.type === "wifi"` | ✅ |

Sostituisce il vecchio `/api/wifi/status`: un solo endpoint, `adapter.type` (`"wifi"` /
`"ethernet"`) dice quale interfaccia è attiva, esattamente come GingerView fa già oggi
derivando `isWired` dallo stesso campo (solo che oggi lo legge da un path che si chiama
"wifi" per un'interfaccia che può essere anche cablata).

## 2. WiFi

| Metodo | Path | Richiesta | Risposta (sintesi) | Stato |
|---|---|---|---|---|
| GET | `/api/network/wifi/networks` | — | Reti visibili: `{ ssid, signalStrength, security, frequency, isHidden }[]` | ✅ |
| POST | `/api/network/wifi/connect` | `{ ssid, password? }` | `{ success, ssid, message, status, currentConnection?, previousConnection? }` | ✅ |
| POST | `/api/network/wifi/disconnect` | — | Stesso shape di `connect` | ✅ |
| POST | `/api/network/wifi/rescan` | — | Forza una nuova scansione (oggi `scanNetworks()` in GingerView riusa `GET /networks`, non esiste un trigger dedicato) | 🆕 |
| GET | `/api/network/wifi/saved` | — | Reti salvate/configurate in precedenza | 🆕 |
| DELETE | `/api/network/wifi/saved/{ssid}` | — | Dimentica una rete salvata | 🆕 |

## 3. Ethernet

| Metodo | Path | Richiesta | Risposta (sintesi) | Stato |
|---|---|---|---|---|
| GET | `/api/network/ethernet/status` | — | Vista dedicata (cavo collegato, IP/MAC, DHCP/statico) | 🆕 |

Su Raspberry Pi l'Ethernet è tipicamente plug-and-play via DHCP: lo stato unificato (punto 1)
copre già il caso d'uso noto. Questo endpoint ha senso solo se serve un dettaglio che
`/api/network/status` non dà (es. per un futuro IP statico via `POST /api/network/ethernet/config`).

## 4. Timezone

| Metodo | Path | Richiesta | Risposta (sintesi) | Stato |
|---|---|---|---|---|
| GET | `/api/timezone` | — | `{ timezone, ntpSynchronized }` — equivalente a `timedatectl show` | ✅ |
| POST | `/api/timezone` | `{ timezone }` | Nuovo stato dopo `timedatectl set-timezone <id>` | ✅ |

Già `camelCase`, nessuna modifica rispetto alla proposta originale. Non serve un endpoint per
l'elenco dei fusi orari validi: GingerView genera già la lista IANA lato client da `zone.tab`
di tzdata; la validazione lato server si limita a controllare che l'id ricevuto sia una zona
nota al sistema (es. che esista `/usr/share/zoneinfo/<timezone>`).

## 5. Onboarding di rete (futuro — non ora)

Non implementato in questa iterazione. Flusso previsto, per quando servirà:

1. All'avvio, se nessuna rete WiFi nota (già salvata) è raggiungibile **e** non c'è
   connessione Ethernet attiva, la macchina apre un proprio Access Point.
2. Un utente si connette all'AP; GingerView mostra un wizard iniziale di selezione/
   configurazione rete.
3. Il wizard è servito da GingerView, ma usa le API di setup/connessione esposte da
   G2-Service — presumibilmente le stesse di `/api/network/wifi/networks` e `/connect` già
   proposte sopra, dato che la funzione è la stessa (scegliere una rete e connettersi).
4. Una volta connessa alla rete scelta, la macchina chiude l'Access Point.

Procedura standard "vecchio stile" di configurazione rete per dispositivi IoT. Punti da
chiarire quando si affronterà l'implementazione (non ora):

- se serve un endpoint esplicito per sapere "sono in modalità AP" (es. un campo `apActive` su
  `/api/network/status`), utile a GingerView per adattare l'interfaccia;
- il comportamento hardware — un solo adattatore WiFi che cambia modalità (AP ↔ client) o due
  interfaccie dedicate come nella versione precedente di G2-Service (rimossa, vedi
  [02 — Architettura](02-architettura.md#stato-attuale)).

---

## Riepilogo

- **Necessari (✅)**: stato di rete unificato, scansione/connessione/disconnessione WiFi,
  lettura/scrittura timezone — 6 endpoint, tutti da implementare con path `/api/network/*`
  (tranne timezone, che resta `/api/timezone`) e corpi in `camelCase`.
- **Da valutare se servono davvero (🆕)**: rescan esplicito, reti salvate/dimentica, stato
  Ethernet dedicato.
- **Futuro, esplicitamente non ora (🔮)**: onboarding di rete via Access Point (punto 5).
