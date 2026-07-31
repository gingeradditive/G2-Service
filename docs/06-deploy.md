# 06 — Deploy

## Come arriva sulla macchina

G2-Service non si installa da solo: viene clonato e installato dal modulo
`modules/generic/69-G2-Service` di [G2-OS](../../G2-OS/) durante la build dell'immagine
Raspberry Pi, che clona il repo in `/home/pi/G2-Service` e lancia `Scripts/install.sh`.

## `Scripts/install.sh`

Eseguito sulla Raspberry Pi (o dal modulo G2-OS durante la build). In ordine:

1. Aggiorna i pacchetti di sistema (`apt update && apt upgrade`), installa Python3/pip/venv.
2. Crea un virtualenv in `venv/` e installa `requirements.txt`.
3. Genera **al volo** `/etc/systemd/system/g2-service.service` (non è un file versionato nel
   repo, viene scritto qui via heredoc): `ExecStart=<venv>/bin/python src/main.py`, utente
   **root**, `Restart=always`. Lo abilita e avvia (`systemctl enable --now g2-service`).
4. Installa `Scripts/g2-service-first-boot.service` (questo sì versionato) e lo abilita —
   vedi sotto.
5. Crea `~/printer_data/config/G2-Configs` come symlink a `Configs/` — vedi
   [04 — Configurazione macchina](04-configurazione-macchina.md).

Il servizio gira come **root** perché deve poter eseguire `nmcli`/`ip` con privilegi elevati
(vedi [02 — Architettura](02-architettura.md#networkmanager-srcapinetworkpy)) — non c'è
sandboxing o riduzione di privilegi.

## Setup Wi-Fi al primo avvio

Flusso a due stadi, pensato per funzionare senza che l'utente abbia già una rete disponibile:

```
boot
  │
  ▼
g2-service-first-boot.service (systemd, oneshot)
  │  ConditionPathExists=!/etc/g2-service/first-boot-completed
  │  attende fino a 60x2s che wlan0 sia disponibile
  ▼
Scripts/first-boot-wifi-setup.sh
  │  chmod +x + esegue setup_wifi_complete.sh
  ▼
Scripts/setup_wifi_complete.sh
  │  1. prepara wlan0 (ferma wpa_supplicant/hostapd/dnsmasq, lo scollega da NetworkManager
  │     in modo persistente via /etc/NetworkManager/conf.d/unmanaged-wlan0.conf)
  │  2. installa hostapd, dnsmasq, iptables(-persistent), nginx, wireless-tools, ...
  │  3. assegna IP statico 192.168.4.1/24 a wlan0 (persistito in /etc/dhcpcd.conf e,
  │     come fallback, in un file systemd-networkd)
  │  4. configura dnsmasq (DHCP 192.168.4.2–192.168.4.20, DNS locale per
  │     mainsail.local/api.local/g2.local/...)
  │  5. genera SSID+password deterministici dal MAC di wlan0 (vedi
  │     03 — Access Point) e configura hostapd (rete nascosta di default, --hidden=false
  │     per renderla visibile)
  │  6. configura iptables: consente tutto il traffico su wlan0 verso i servizi locali,
  │     blocca il forwarding verso l'interfaccia con accesso a internet, DNAT verso
  │     Moonraker (127.0.0.1:7125) per i client che raggiungono 192.168.4.1:7125
  │  7. configura un vhost nginx dedicato su 192.168.4.1:80, che fa da reverse proxy:
  │       /            → Mainsail/GingerView (file statici)
  │       /g2/, /docs  → G2-Service (127.0.0.1:8080)
  │       /api, /printer → Moonraker (127.0.0.1:7125)
  │       /websocket   → Moonraker WebSocket
  │  8. salva le credenziali in /home/pi/ap_credentials.txt (letto da
  │     GET /api/access-point/info, vedi 03)
  │  9. avvia/verifica hostapd, dnsmasq, G2-Service; genera un QR code Wi-Fi
  │     (richiede qrencode + ImageMagick, installati al volo se mancanti)
  ▼
first-boot-wifi-setup.sh segna /etc/g2-service/first-boot-completed
  e disabilita g2-service-first-boot.service (non gira più ai boot successivi)
```

Da questo momento la macchina espone un hotspot **nascosto** (SSID non broadcast di default)
su cui l'utente può collegarsi con le credenziali stampate nei log di systemd
(`journalctl -u g2-service-first-boot`) o lette via `/api/access-point/info`, e da lì
raggiungere Mainsail/GingerView, Swagger UI e Moonraker sulla porta 80 senza bisogno di
ricordare porte diverse.

Se l'utente vuole ripetere il setup manualmente (es. dopo un problema), lo script si può
rilanciare a mano:

```bash
sudo /home/pi/G2-Service/Scripts/setup_wifi_complete.sh [--hidden=true|false]
```

## Deploy in sviluppo (`Scripts/deploy.sh`)

Script di comodo per sincronizzare il codice locale su una macchina già installata, via
`rsync` + riavvio del servizio via SSH:

```bash
export DISCOVERY_HOST="192.168.1.194"   # IP o hostname della macchina target
./Scripts/deploy.sh
```

Da tenere presente:
- l'host è **hardcoded** nello script (`192.168.1.194`), da editare a mano per puntare a una
  macchina diversa — la riga precedente che imposta `discovery.local` viene sovrascritta
  subito dopo, quindi non ha effetto;
- riavvia un servizio chiamato **`fastapi-app`** via `systemctl restart fastapi-app` — nome
  che **non corrisponde** al servizio creato da `install.sh` (`g2-service`, vedi sopra).
  Sulla macchina di destinazione deve esistere un unit `fastapi-app` per far funzionare
  questo script così com'è, altrimenti il riavvio fallisce silenziosamente dal punto di vista
  di chi lancia `deploy.sh` (l'errore compare solo nell'output SSH). Vedi
  [07 — Stato attuale](07-stato-attuale.md#nome-del-servizio-systemd-incoerente-tra-installsh-e-deploysh).

C'è anche un `deploy.sh` alla radice del repo: è un **symlink rotto** (punta a un percorso
che non esiste più dopo una riorganizzazione delle cartelle) — usa `Scripts/deploy.sh`
direttamente. Dettagli in [07](07-stato-attuale.md#symlink-deploysh-rotto).

## Riavviare/ispezionare il servizio in produzione

```bash
sudo systemctl status g2-service
sudo systemctl restart g2-service
sudo journalctl -u g2-service -f

# log del setup Wi-Fi al primo boot
sudo journalctl -u g2-service-first-boot
cat /var/log/wifi_setup.log
```
