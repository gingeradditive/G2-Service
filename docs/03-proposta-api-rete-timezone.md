# 03 — API: Rete e Timezone

> Contratto **deciso e approvato**, non ancora implementato. Le convenzioni trasversali
> (prefisso `/service`, `camelCase`, modello degli errori, job asincroni) stanno in
> [02 — Architettura](02-architettura.md#convenzioni-comuni-a-tutte-le-api) e non si ripetono qui.

## Hardware su cui si appoggia

La G2 ha **un solo adattatore WiFi**, quello integrato del Raspberry Pi 4: `wlan0`. Non c'è
nessuna chiavetta USB aggiuntiva (il vecchio codice, rimosso, assumeva erroneamente un `wlan1`
per il client e `wlan0` riservato all'Access Point).

Due conseguenze importanti:

- tutte le operazioni WiFi lavorano su `wlan0`;
- l'Access Point futuro (punto 6) e la connessione client sono **mutuamente esclusivi**: la
  stessa interfaccia non può fare entrambe le cose. Mentre l'AP è attivo la macchina non è
  connessa a nessuna rete e la scansione non è affidabile.

L'interfaccia Ethernet è `eth0`. Entrambi i nomi sono fissi nel codice: sono hardware noto e
stabile, non serve rilevarli a runtime.

---

## 1. Stato di rete (unificato)

| Metodo | Path | Richiesta | Risposta |
|---|---|---|---|
| GET | `/service/network/status` | — | vedi sotto |

```json
{
  "adapter": { "device": "eth0", "type": "ethernet", "state": "connected", "connection": "Wired connection 1" },
  "ip": { "ipv4": "192.168.1.42", "ipv6": "...", "mac": "..." },
  "signalInfo": null,
  "interfaces": [ { "device": "eth0", "type": "ethernet", "state": "connected" },
                  { "device": "wlan0", "type": "wifi", "state": "disconnected" } ]
}
```

- `adapter` descrive la connessione **attiva**. Se sono attive entrambe, vince l'**Ethernet**:
  è quella che il sistema usa di default ed è la risposta più utile da mostrare all'utente.
- Se non c'è **nessuna** connessione, `adapter.state` vale esplicitamente `"disconnected"` (non
  campi nulli o oggetto assente), `ip` ha i campi a `null` e `connection` a `null`.
- `signalInfo` (`{ signalStrength, ssid }`) è presente **solo** quando `adapter.type` è
  `"wifi"`; negli altri casi è `null`.
- `interfaces` elenca tutte le interfacce note anche quando non sono attive: serve a GingerView
  per distinguere "non c'è il cavo" da "il cavo c'è ma non prende".

## 2. WiFi

| Metodo | Path | Richiesta | Risposta | Tipo |
|---|---|---|---|---|
| GET | `/service/network/wifi/networks` | — | `{ ssid, signalStrength, security, frequency, isHidden }[]` | sincrono |
| POST | `/service/network/wifi/rescan` | — | elenco aggiornato, stesso shape di `networks` | sincrono |
| POST | `/service/network/wifi/connect` | `{ ssid, password? }` | `202` + job | **asincrono** |
| POST | `/service/network/wifi/disconnect` | — | `202` + job | **asincrono** |
| GET | `/service/network/wifi/saved` | — | `{ ssid, autoconnect, lastUsed }[]` | sincrono |
| DELETE | `/service/network/wifi/saved/{ssid}` | — | `204`, oppure `404 NOT_FOUND` | sincrono |

`connect` e `disconnect` restituiscono un job (vedi
[02 — Operazioni lunghe](02-architettura.md#operazioni-lunghe-modello-a-job-asincroni)): la
connessione HTTP corrente può cadere perché l'IP della macchina cambia.

**Esiti possibili del job `wifi.connect`**: `succeeded`, oppure `failed` con
`WIFI_AUTH_FAILED` (password sbagliata), `WIFI_NETWORK_NOT_FOUND` (SSID non trovato in
scansione), `WIFI_TIMEOUT` (associazione non completata entro il limite).

### Disconnessione e riconnessione automatica

`disconnect` **spegne anche l'autoconnect** della connessione, oltre ad abbassarla. Senza
questo, NetworkManager si riconnetterebbe da solo dopo pochi secondi e l'utente vedrebbe il
comando "non funzionare".

Simmetricamente, `connect` **riattiva l'autoconnect** sulla rete a cui ci si connette. La rete
resta comunque salvata: "disconnetti" non è "dimentica" — per rimuoverla del tutto c'è
`DELETE /service/network/wifi/saved/{ssid}`.

## 3. Ethernet

| Metodo | Path | Richiesta | Risposta |
|---|---|---|---|
| GET | `/service/network/ethernet/status` | — | `{ device, cableConnected, state, ip: { ipv4, ipv6, mac }, addressing }` |

`addressing` vale `"dhcp"` o `"static"`. `cableConnected` riflette lo stato del link fisico
(distingue "cavo staccato" da "cavo attaccato ma senza IP"), che lo stato unificato del punto 1
non dà.

Non è previsto un endpoint per impostare un IP statico: se servirà si aggiungerà un
`POST /service/network/ethernet/config`.

## 4. Timezone

| Metodo | Path | Richiesta | Risposta |
|---|---|---|---|
| GET | `/service/timezone` | — | `{ timezone, ntpSynchronized }` |
| POST | `/service/timezone` | `{ timezone }` | Stesso shape, dopo `timedatectl set-timezone` |

`ntpSynchronized` è in **sola lettura**. Non esiste un endpoint per abilitare/disabilitare NTP
o per impostare l'ora a mano: su Raspberry Pi OS la sincronizzazione è attiva di default e il
Pi non ha un RTC, quindi appena c'è rete l'ora si corregge da sola. Impostare l'ora a mano
sarebbe utile solo su una macchina permanentemente offline — caso che oggi non esiste. Se
servirà, si aggiungerà.

Un `timezone` non riconosciuto dal sistema (non esiste `/usr/share/zoneinfo/<timezone>`) è
`400 INVALID_INPUT`. L'elenco delle zone valide **non** viene esposto: GingerView lo genera già
lato client da `zone.tab` di tzdata.

## 5. Health

| Metodo | Path | Richiesta | Risposta |
|---|---|---|---|
| GET | `/service/health` | — | vedi sotto |

```json
{
  "status": "ok",
  "version": "0.1.0",
  "checks": { "networkManager": true, "timedatectl": true, "serialConfigured": false }
}
```

È il modo in cui GingerView capisce se G2-Service è presente e quale versione parla, ed è utile
per diagnosticare una macchina da remoto. `status` resta `"ok"` anche se qualche `check` è
`false`: il servizio è vivo, semplicemente una funzionalità non è disponibile su quella
macchina. `version` è la versione del pacchetto, la stessa che Moonraker mostra nell'update
manager.

L'endpoint attuale è `GET /health`: va spostato sotto il prefisso `/service` insieme al resto.

## 6. Onboarding di rete (futuro — non ora)

Non implementato. Flusso previsto:

1. All'avvio, se nessuna rete WiFi salvata è raggiungibile **e** non c'è connessione Ethernet,
   la macchina apre un Access Point su `wlan0`.
2. Un utente si connette all'AP; GingerView mostra un wizard di selezione rete.
3. Il wizard usa gli stessi endpoint di scansione e connessione già definiti al punto 2.
4. Connessa la rete scelta, l'AP si chiude.

Con un solo adattatore (vedi sopra) l'AP e la modalità client si escludono a vicenda: passare
in modalità AP significa staccarsi da qualsiasi rete, e la scansione mentre l'AP è attivo
richiede attenzioni particolari. Va inoltre aggiunto un modo per sapere che la macchina è in
modalità AP — presumibilmente un campo `apActive` su `/service/network/status`, così GingerView
può mostrare il wizard invece della pagina di rete normale.
