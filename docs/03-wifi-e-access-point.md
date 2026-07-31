# 03 — Wi-Fi e Access Point

Riferimento completo degli endpoint `/api/wifi/*` e `/api/access-point/*`, ricavato da
`src/api/app.py` e `src/api/network.py`. Sostituisce il precedente `docs/wifi-api.md`, che
copriva solo tre dei dodici endpoint reali e riportava una base URL (`:8000`) non più
corretta — vedi [07 — Stato attuale](07-stato-attuale.md).

Base URL locale: `http://localhost:8080` in sviluppo, `http://<ip-macchina>:8080` in rete,
`http://192.168.4.1:8080` (o via nginx su `http://192.168.4.1/g2/`) quando la macchina è in
modalità Access Point di primo setup.

## Prerequisiti

Gli endpoint Wi-Fi richiedono **NetworkManager** installato e attivo sulla macchina:

```bash
sudo apt-get update && sudo apt-get install network-manager
sudo systemctl enable --now NetworkManager
sudo systemctl status NetworkManager
```

Senza NetworkManager (o su macOS in sviluppo), le chiamate cadono in un fallback che
restituisce **dati finti** — vedi [02 — Architettura](02-architettura.md#networkmanager-srcapinetworkpy)
e [05 — Sviluppo](05-sviluppo.md).

## Wi-Fi

### `GET /api/wifi/networks`

Scansiona e restituisce le reti Wi-Fi visibili sull'interfaccia `wlan1`.

```bash
curl http://localhost:8080/api/wifi/networks
```

```json
[
  {
    "ssid": "MyNetwork",
    "signal_strength": 85,
    "security": "WPA2",
    "frequency": 2412,
    "is_hidden": false
  }
]
```

Campi: `ssid` (string), `signal_strength` (int 0–100, opzionale), `security` (string,
opzionale — vuoto se rete aperta), `frequency` (int, MHz, opzionale), `is_hidden` (bool,
attualmente sempre `false`: il parsing da `nmcli` non popola mai questo campo).

Errori: `500` se `wlan1` non esiste o `nmcli`/fallback falliscono entrambi.

### `GET /api/wifi/status`

```bash
curl http://localhost:8080/api/wifi/status
```

```json
{
  "adapter": {
    "device": "wlan1",
    "type": "wifi",
    "state": "connected",
    "connection": "MyNetwork"
  },
  "ip": {
    "ipv4": "192.168.1.42",
    "ipv6": null,
    "mac": "aa:bb:cc:dd:ee:ff"
  },
  "signal_info": {
    "current_signal": 85,
    "available_networks": 6,
    "signal_range": "20% - 85%",
    "current_connection_signal": 85,
    "current_ssid": "MyNetwork"
  }
}
```

Nota: la vecchia `docs/wifi-api.md` mostrava una risposta piatta (`device`, `state`,
`connection` alla radice); la struttura reale è annidata sotto `adapter`/`ip`/`signal_info`
come sopra.

### `POST /api/wifi/rescan`

```bash
curl -X POST http://localhost:8080/api/wifi/rescan
```

```json
{ "success": true, "message": "WiFi rescan triggered" }
```

### `POST /api/wifi/connect`

```bash
curl -X POST http://localhost:8080/api/wifi/connect \
  -H "Content-Type: application/json" \
  -d '{"ssid": "MyNetwork", "password": "secret123"}'
```

Corpo: `ssid` (obbligatorio), `password` (opzionale — omettilo per reti aperte).

Comportamento: verifica che la rete sia tra quelle visibili, disconnette e rimuove
un'eventuale connessione preesistente con lo stesso nome, poi tenta la connessione diretta
(`nmcli device wifi connect`); se fallisce, tenta una configurazione manuale
(`connection add` + `modify` + `up`). Attende 3 secondi e verifica lo stato risultante.

```json
{
  "success": true,
  "ssid": "MyNetwork",
  "message": "Successfully connected to MyNetwork",
  "status": "connected"
}
```

In caso di fallimento risponde comunque `200` con `"success": false` (l'eccezione viene
catturata internamente), non `500` — a differenza degli altri endpoint.

### `POST /api/wifi/disconnect`

```bash
curl -X POST http://localhost:8080/api/wifi/disconnect
```

```json
{
  "success": true,
  "previous_connection": "MyNetwork",
  "message": "Successfully disconnected from MyNetwork",
  "status": "disconnected"
}
```

### `GET /api/wifi/saved-networks`

```bash
curl http://localhost:8080/api/wifi/saved-networks
```

```json
{
  "saved_networks": [
    {
      "name": "MyNetwork",
      "type": "802-11-wireless",
      "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "timestamp": "1700000000",
      "autoconnect": true
    }
  ]
}
```

### `DELETE /api/wifi/saved-networks/{ssid}`

Il parametro di path è dichiarato `{ssid:path}`, quindi accetta SSID con caratteri speciali
(inclusi `/`) senza bisogno di URL-encoding aggressivo.

```bash
curl -X DELETE http://localhost:8080/api/wifi/saved-networks/MyNetwork
```

Se la rete risulta connessa, la disconnette prima di eliminarla. Risponde `404`-like nel
corpo (`"status": "not_found"`, HTTP comunque `200`) se il nome non esiste tra le reti
salvate.

### `POST /api/wifi/forget-network`

Alias semantico di delete: stessa logica di `DELETE /api/wifi/saved-networks/{ssid}`, con
messaggi di risposta diversi (`"forgotten"` invece di `"deleted"`). Prende `ssid` nel corpo
invece che nel path.

```bash
curl -X POST http://localhost:8080/api/wifi/forget-network \
  -H "Content-Type: application/json" \
  -d '{"ssid": "MyNetwork"}'
```

## Access Point di primo setup

### `GET /api/access-point/info`

Restituisce le credenziali dell'Access Point (lette da `/home/pi/ap_credentials.txt`,
generato da `Scripts/setup_wifi_complete.sh` — vedi [06 — Deploy](06-deploy.md)) più lo stato
in tempo reale di `wlan0` (`hostapd` attivo, IP assegnato, client connessi).

```bash
curl http://localhost:8080/api/access-point/info
```

```json
{
  "available": true,
  "access_point": {
    "ssid": "G2TabletNetwork-a1b2c3",
    "password": "G2xxxxxxxxxxxxxxxx",
    "ip_address": "192.168.4.1",
    "interface": "wlan0",
    "country": "IT",
    "network_type": "Hidden",
    "ip_range": "192.168.4.2-192.168.4.20"
  },
  "testing_steps": ["1. Connect a device to the network '...'", "..."],
  "notes": ["This is a hidden network - SSID is not broadcasted", "..."],
  "ap_status": {
    "interface_available": true,
    "ap_active": true,
    "status": "working",
    "interface": "wlan0",
    "ip_address": "192.168.4.1",
    "mode": "Master",
    "clients": [{"ip": "192.168.4.5", "mac": "aa:bb:cc:11:22:33"}],
    "hostapd_running": true,
    "interface_up": true
  },
  "status_message": "Access Point is working correctly"
}
```

Se il file delle credenziali non esiste ancora (macchina non ha mai completato il primo
setup), risponde con `"available": false` e un messaggio che rimanda a
`setup_wifi_complete.sh`.

`ssid`/`password` generati da `Scripts/setup_wifi_complete.sh` a partire dal MAC di `wlan0`:
- SSID: `G2TabletNetwork-<ultimi 6 caratteri esadecimali del MAC>`
- Password: `G2` + primi 16 caratteri di `sha256(mac_senza_due_punti)`

Deterministico per macchina, non segreto (chiunque conosca il MAC può ricalcolarlo) — accettabile
per un hotspot di setup temporaneo e locale, non pensato come misura di sicurezza forte.

## Note generali

- Nessun endpoint richiede autenticazione: chiunque sia in rete con la macchina (o connesso
  all'AP di setup) può leggere reti salvate, disconnettere il Wi-Fi o modificare la
  configurazione. Accettabile nel contesto attuale (LAN/AP locale, nessuna esposizione
  internet), ma da tenere presente se lo scenario d'uso cambia.
- Gli errori interni (eccezioni non gestite più a monte) diventano `HTTP 500` con
  `detail` testuale — utile per debug, ma espone dettagli implementativi (comandi `nmcli`,
  stderr) al chiamante.
- Per un elenco endpoint navigabile interattivamente, usa Swagger UI (`/docs`) quando c'è
  connessione internet per gli asset, oppure `/docs-offline` per la versione statica —
  quest'ultima non è però aggiornata a tutti gli endpoint qui sopra, vedi
  [07 — Stato attuale](07-stato-attuale.md#docs-offline-fuori-sincrono).
