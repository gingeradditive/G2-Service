# 03 — Proposta API: Rete e Timezone

> Questa è una **proposta di lavoro**, non una specifica congelata: elenca gli endpoint che
> G2-Service potrebbe esporre per rete (WiFi/Ethernet) e timezone, da discutere e affinare
> prima di implementare. Nessuno di questi endpoint esiste ancora nel codice (vedi
> [02 — Architettura](02-architettura.md#stato-attuale)).

## Legenda

- 🔗 **Già atteso da GingerView** — il path e la forma dei dati sono già hardcoded nel client
  (`network-api.ts` / `timezone.ts`). Implementarli così com'è significa zero modifiche lato
  GingerView. Cambiare path o forma richiede invece di aggiornare anche GingerView.
- 🆕 **Proposta nuova** — non richiesta da nessun consumer esistente, da valutare se serve
  davvero prima di implementarla.

## Convenzioni generali (da confermare)

- Nessuna autenticazione, coerente con Moonraker su G2-OS (che gira senza auth) — vedi
  [01 — Panoramica](01-panoramica.md).
- Errori di validazione nel formato di default FastAPI: `{"detail": [{"loc", "msg", "type"}]}`
  — è già il formato che GingerView si aspetta (`HTTPValidationError` in `wifi.ts`).
- **Attenzione a un'incoerenza già presente nel contratto atteso da GingerView**: i tipi WiFi
  usano `snake_case` (`signal_strength`, `is_hidden`), i tipi timezone usano `camelCase`
  (`ntpSynchronized`). Non è qualcosa che possiamo correggere unilateralmente senza toccare
  GingerView — va deciso consapevolmente se uniformare (e su quale convenzione) o accettare
  l'inconsistenza perché già "cablata" nei due client.

---

## 1. WiFi

| Metodo | Path | Richiesta | Risposta (sintesi) | Stato |
|---|---|---|---|---|
| GET | `/api/wifi/status` | — | Adattatore, IP, MAC, segnale, SSID corrente (vedi `NetworkStatus`) | 🔗 |
| GET | `/api/wifi/networks` | — | Elenco reti visibili: `ssid`, `signal_strength`, `security`, `frequency`, `is_hidden` | 🔗 |
| POST | `/api/wifi/connect` | `{ ssid, password? }` | Esito connessione: `success`, `status`, `message`, ... | 🔗 |
| POST | `/api/wifi/disconnect` | — | Esito disconnessione | 🔗 |
| POST | `/api/wifi/rescan` | — | Forza una nuova scansione (oggi `scanNetworks()` in GingerView riusa `GET /networks`, non esiste un trigger dedicato) | 🆕 |
| GET | `/api/wifi/saved` | — | Reti salvate/configurate in precedenza | 🆕 |
| DELETE | `/api/wifi/saved/{ssid}` | — | Dimentica una rete salvata | 🆕 |

**Nota — `adapter.type` come discriminante wifi/wired.** GingerView deriva già `isWired` dal
campo `adapter.type` della risposta di `GET /api/wifi/status` (`connectionType.toLowerCase()
!== 'wifi'`), nonostante il path si chiami `/api/wifi/status`. In pratica quell'endpoint è già
pensato per essere uno **stato di rete generico**, non solo WiFi — vedi punto 3.

**Domanda aperta — modalità Access Point per il primo setup.** La versione precedente (rimossa,
vedi [02 — Architettura](02-architettura.md#stato-attuale)) esponeva un Access Point su
un'interfaccia dedicata per configurare il WiFi la prima volta, senza rete disponibile. Va
deciso se questo flusso di onboarding serve ancora nello scope attuale o se si assume che il
Raspberry Pi abbia sempre un modo di essere raggiunto (es. Ethernet) per la prima
configurazione.

## 2. Ethernet

| Metodo | Path | Richiesta | Risposta (sintesi) | Stato |
|---|---|---|---|---|
| GET | `/api/ethernet/status` | — | Cavo collegato, IP/MAC, tipo di indirizzamento (DHCP/statico) | 🆕 |

Su Raspberry Pi l'Ethernet è tipicamente plug-and-play via DHCP: non è chiaro se serva altro
oltre a uno stato in sola lettura (nessun consumer lo richiede oggi). Se in futuro serve un IP
statico, si aggiungerebbe un `POST /api/ethernet/config`.

## 3. Stato di rete unificato

| Metodo | Path | Richiesta | Risposta (sintesi) | Stato |
|---|---|---|---|---|
| GET | `/api/network/status` | — | Panoramica di tutte le interfacce (wifi + ethernet), quale è "attiva" | 🆕 |

Alternativa a mantenere `/api/wifi/status` come endpoint "furbo" che risponde anche quando è
collegato via cavo (comportamento già assunto da GingerView oggi, vedi nota sopra). Va scelto
**uno dei due**, non entrambi: o si rinomina il contratto esistente in qualcosa di più onesto
come `/api/network/status` (richiede update di GingerView), oppure si tiene `/api/wifi/status`
come nome storico anche per lo stato generico (evita l'update lato client, path meno chiaro).

## 4. Timezone

| Metodo | Path | Richiesta | Risposta (sintesi) | Stato |
|---|---|---|---|---|
| GET | `/api/timezone` | — | `{ timezone, ntpSynchronized }` — equivalente a `timedatectl show` | 🔗 |
| POST | `/api/timezone` | `{ timezone }` | Nuovo stato dopo `timedatectl set-timezone <id>` | 🔗 |

**Non serve un endpoint per l'elenco dei fusi orari validi** (es. `GET
/api/timezone/available`): GingerView genera già la lista IANA lato client da `zone.tab` di
tzdata (vedi la sua documentazione, `05-sviluppo.md#dati-generati-fusi-orari-e-mappa`), quindi
la validazione può avvenire lato server semplicemente verificando che l'id ricevuto sia una
zona nota al sistema (es. che esista `/usr/share/zoneinfo/<timezone>`).

---

## Riepilogo — cosa è vincolante e cosa no

- **Vincolante per compatibilità immediata con GingerView**: i 6 endpoint 🔗 (4 WiFi + 2
  timezone), con la forma dati esatta già definita nei tipi TypeScript del client.
- **Da decidere prima di scrivere codice**: le tre domande aperte sopra (naming
  snake_case/camelCase, Access Point per il first-setup, `/api/wifi/status` vs
  `/api/network/status`).
- **Da valutare se servono davvero**: rescan esplicito, reti salvate/dimentica, stato Ethernet
  dedicato — nessuna è richiesta da un consumer esistente oggi.
