# 03 — API: Rete e Timezone

> Contratto **deciso e approvato** e **interamente implementato** (i punti 1-5; il 6 è futuro).
> Le convenzioni trasversali
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

## Due trappole di `nmcli`

Valgono per tutti gli endpoint di rete e sono la ragione per cui il wrapper sta in un modulo
suo (`services/network/nmcli.py`), con le funzioni di parsing pure e verificabili su output
finto.

1. **`nmcli` è tradotto.** Con `LANG` italiano `device status` stampa `connesso`, e ogni
   confronto nel codice fallisce. Tutti i comandi girano con `LC_ALL=C`.
2. **In `--terse` i due punti dentro un valore sono protetti con `\`** (un MAC diventa
   `B8\:27\:EB\:...`). Uno `split(":")` funziona finché non arriva un SSID con i due punti
   dentro, e allora sbaglia in silenzio.

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

`state` vale `connected`, `connecting`, `disconnected`, `unavailable`, `unmanaged` oppure
`unknown`. È la distinzione fra `disconnected` e `unavailable` a portare l'informazione che
serve a GingerView: su Ethernet `unavailable` vuol dire **cavo staccato**, `disconnected` vuol
dire cavo attaccato ma nessuna connessione attiva. Uno stato che NetworkManager introdurrà in
futuro diventa `unknown` e non un errore.

**Quale interfaccia finisce in `adapter` quando non c'è niente di connesso.** Si ordina per
stato — chi è più vicino a essere connesso vince — e a parità di stato passa avanti
l'Ethernet. Con il cavo staccato (`unavailable`) e il WiFi libero (`disconnected`) l'adapter è
quindi `wlan0`: è quella su cui l'utente può agire.

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
scansione), `WIFI_TIMEOUT` (associazione non completata entro il limite). Il `result` di un
job riuscito è `{ ssid, ip: { ipv4, ipv6, mac } }` per `connect` e
`{ ssid, alreadyDisconnected }` per `disconnect`.

### Come sono fatti i campi dell'elenco reti

- `security` è `"open"` per le reti senza cifratura, altrimenti la stringa di NetworkManager
  (`"WPA2"`, `"WPA1 WPA2"`, `"WPA3"`, ...). Un client che deve decidere se chiedere la
  password controlla `security === "open"`.
- `frequency` è in MHz (`2412`, `5180`), `null` se non leggibile.
- Uno stesso SSID compare **una volta sola**, con il segnale migliore: senza questo un elenco
  da mostrare all'utente conterrebbe una riga per access point, cioè due per ogni rete
  dual-band e altrettante per ogni ripetitore.
- Le reti nascoste hanno `ssid: ""` e `isHidden: true`.

### Password e profili salvati

Quando `connect` riceve una `password` e una connessione per quello SSID è già salvata, il
profilo viene **ricreato**. Non è un dettaglio implementativo evitabile: `nmcli` riuserebbe il
profilo esistente ignorando la password appena ricevuta, e chi sta correggendo una password
sbagliata resterebbe bloccato sul vecchio valore senza capire perché. Simmetricamente, un
tentativo fallito non lascia dietro di sé una rete "salvata" a cui non ci si è mai connessi.

### Disconnessione e riconnessione automatica

`disconnect` **spegne anche l'autoconnect** della connessione, oltre ad abbassarla. Senza
questo, NetworkManager si riconnetterebbe da solo dopo pochi secondi e l'utente vedrebbe il
comando "non funzionare". L'ordine dei due passi conta — prima l'autoconnect, poi
l'abbassamento — perché al contrario NetworkManager fa in tempo a riagganciare nel mezzo.

Per lo stesso motivo si abbassa l'**interfaccia** e non solo la connessione: con la sola
connessione giù, NetworkManager sarebbe libero di agganciare subito un'altra rete salvata, e
per l'utente sarebbe come non essersi disconnesso affatto.

Simmetricamente, `connect` **riattiva l'autoconnect** sulla rete a cui ci si connette. La rete
resta comunque salvata: "disconnetti" non è "dimentica" — per rimuoverla del tutto c'è
`DELETE /service/network/wifi/saved/{ssid}`.

## 3. Ethernet

| Metodo | Path | Richiesta | Risposta |
|---|---|---|---|
| GET | `/service/network/ethernet/status` | — | `{ device, cableConnected, state, ip: { ipv4, ipv6, mac }, addressing }` |

`addressing` vale `"dhcp"` o `"static"`, e `null` quando non c'è una connessione attiva da cui
leggerlo (a cavo staccato non esiste una risposta vera). `cableConnected` riflette lo stato del
link fisico (distingue "cavo staccato" da "cavo attaccato ma senza IP"), che lo stato unificato
del punto 1 non dà.

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

Un identificativo *malformato* è invece `422`, cioè un normale errore di validazione di
FastAPI. La divisione segue la tabella di [02](02-architettura.md#modello-degli-errori): la
sintassi è `422`, "sintatticamente valido ma non accettabile" è `400`.

**Quella stringa diventa un percorso**, quindi il formato è vincolato a
`^[A-Za-z0-9+_-]+(?:/[A-Za-z0-9+_-]+)*$`: il punto non è fra i caratteri ammessi e questo
esclude alla radice i `..` di una path traversal. Il controllo è ripetuto dentro il servizio e
non lasciato solo allo schema.

Si legge da `timedatectl show` e non da `timedatectl status`: il primo è la forma pensata per
essere interpretata da un programma — `Chiave=valore`, nomi stabili, niente traduzioni — il
secondo è impaginato per una persona e cambia con la lingua di sistema. Se `timedatectl` non
risponde o non riporta il fuso, l'endpoint dà `503 SYSTEM_TOOL_UNAVAILABLE`: non esiste un
ripiego onesto, e rispondere "UTC" quando non lo sappiamo sarebbe un dato su cui l'utente
potrebbe agire.

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

I tre `check` non sollevano mai: un comando assente vale `false`. `/service/health` deve
rispondere anche su una macchina messa male — è lì che serve di più.

È l'unico endpoint di questo documento già implementato.

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
