# 01 — Panoramica

## Cos'è

G2-Service è il servizio Python/FastAPI che gira **sulla Raspberry Pi della stampante Ginger
G2**, accanto a Moonraker/Kalico (il firmware Klipper-derivato per l'estrusione a pellet).
Non è un backend generico: fa solo le cose che non competono al firmware o a Moonraker.

Nel codice reale (`src/`), oggi fa due cose:

1. **Gestione Wi-Fi della macchina** — scansione reti, connessione, disconnessione, reti
   salvate — tramite NetworkManager (`nmcli`) sull'interfaccia `wlan1`. Consumato da
   [GingerView](../../GingerView/) nella pagina Impostazioni → Rete
   (`src/lib/services/network-api.ts`).
2. **Access Point di primo avvio** — al primo boot, se non c'è ancora una rete configurata,
   la macchina apre un hotspot Wi-Fi nascosto su `wlan0` (SSID/password generati dal MAC
   address) per permettere la configurazione iniziale da tablet o telefono senza bisogno di
   una rete esistente. Vedi [06 — Deploy](06-deploy.md).

Il repository ospita anche **la configurazione macchina vera e propria**: `Configs/*.cfg`
(macro Klipper/Kalico per riscaldatori, estrusore a 3 zone, feeder, buzzer, probe) e
`printer.cfg` (non tracciato in git, specifico per ogni macchina). Non è solo codice di
servizio — vedi [04 — Configurazione macchina](04-configurazione-macchina.md).

## Cosa NON fa (ancora)

Il `README.md` alla radice del repo descrive gestione impostazioni macchina, aggiornamenti
firmware, autenticazione JWT, un modello a database (SQLAlchemy/Alembic) e una cartella
`tests/`. **Nessuna di queste cose esiste nel codice attuale.** Sembra scritto come
documentazione "da manuale prodotto" per una versione più matura del servizio che non è mai
stata implementata, o descrive un piano non ancora realizzato. Dettagli in
[07 — Stato attuale](07-stato-attuale.md).

## Dove vive nell'ecosistema

```
G2-OS (immagine Raspberry Pi: Kalico + Moonraker + nginx)
  │ installa (modulo 69-G2-Service)
  ▼
G2-Service ◄──── HTTP same-origin (/api/wifi/*) ──── GingerView (SPA nel browser)
  │
  │ legge/scrive
  ▼
Configs/*.cfg, printer.cfg ──── inclusi da ──── Moonraker → Kalico
```

Per la mappa completa dei repository correlati (G2-OS, GingerView, G2-MultiZoneBed) vedi
[G2/README.md](../../README.md), il file di contesto che vive fuori da questo repo.

## Stack tecnico

- **Python 3** + **FastAPI** + **Uvicorn** (server ASGI)
- **Pydantic** per i modelli delle richieste/risposte Wi-Fi
- **NetworkManager** (`nmcli`) come interfaccia di sistema per il Wi-Fi; `iwlist` come
  fallback; dati finti (mock) come ultimo fallback quando nessuno dei due è disponibile
  (utile per sviluppare su macOS — vedi [05 — Sviluppo](05-sviluppo.md))
- **hostapd** + **dnsmasq** + **nginx** + **iptables** per l'Access Point di primo avvio
  (configurati a runtime da `Scripts/setup_wifi_complete.sh`, non da G2-Service stesso)
- **systemd** per l'avvio del servizio e del setup al primo boot

La porta di ascolto del server FastAPI è **8080** (bind `0.0.0.0`). È stata `8000` in
passato — vedi la nota sulle tracce rimaste di quel cambio in
[07 — Stato attuale](07-stato-attuale.md#riferimenti-alla-vecchia-porta-8000).
