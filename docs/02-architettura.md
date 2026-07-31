# 02 — Architettura

## G2-Service nello stack G2

Tutto gira sullo stesso Raspberry Pi 4 (G2-OS), come processi separati:

```
Raspberry Pi 4 (G2-OS)
├── Kalico           firmware (fork Klipper) — comunica con la scheda via UART
├── Moonraker        API/websocket per Kalico — stato macchina, file, macro, update manager
├── Mainsail         interfaccia web stock di Moonraker
├── GingerView       interfaccia utente custom (SPA statica) — parla con Moonraker e con
│                     G2-Service, non con Kalico direttamente
├── Nginx            reverse proxy, punto d'ingresso unico
└── G2-Service       questo progetto — API per rete e timezone dell'host
```

G2-Service non ha dipendenze verso Kalico/Moonraker/Mainsail e viceversa: comunica
direttamente con il sistema operativo del Raspberry Pi (NetworkManager, `timedatectl`, ...),
non con la stampante.

## Stack tecnico

| Livello | Tecnologia |
|---|---|
| Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Server ASGI | [uvicorn](https://www.uvicorn.org/) |
| Documentazione API | Swagger UI (`/docs`) e ReDoc (`/redoc`), generati automaticamente da FastAPI a partire dallo schema OpenAPI |

## Stato attuale

Il progetto non è mai arrivato in produzione ed è stato azzerato: la versione precedente
(gestione WiFi via `nmcli`, Access Point, script di deploy/systemd, config Klipper/Mainsail
committate nel repo) è stata rimossa — resta consultabile nella cronologia git se serve come
riferimento, ma non va considerata uno stato da cui ripartire.

Oggi il progetto espone un solo endpoint:

- `GET /health` — health check

Rete, timezone e configurazioni stampante (vedi
[01 — Panoramica](01-panoramica.md#ambito-scope)) sono ancora da progettare e implementare.

## Struttura del repository

```
G2-Service/
├── README.md
├── requirements.txt
├── docs/
└── src/
    ├── __init__.py
    └── main.py          # app FastAPI + endpoint /health
```
