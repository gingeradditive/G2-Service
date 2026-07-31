# Documentazione G2-Service

Documentazione tecnica del repository, scritta leggendo il codice reale in `src/`, gli
script in `Scripts/`, i config in `Configs/` e la cronologia git — non il `README.md` alla
radice, che descrive in buona parte funzionalità mai implementate (vedi
[07 — Stato attuale](07-stato-attuale.md)).

## Indice

1. [Panoramica](01-panoramica.md) — cos'è G2-Service, dove vive nell'ecosistema G2
2. [Architettura](02-architettura.md) — struttura del codice, endpoint reali, come è cablato con nginx/AP/Moonraker
3. [Wi-Fi e Access Point](03-wifi-e-access-point.md) — riferimento completo dell'API `/api/wifi/*` e `/api/access-point/*`
4. [Configurazione macchina](04-configurazione-macchina.md) — i file Kalico/Klipper ospitati in `Configs/` e `printer.cfg`
5. [Sviluppo](05-sviluppo.md) — ambiente locale, avvio, test, differenze macOS/Raspberry Pi
6. [Deploy](06-deploy.md) — installazione su Raspberry Pi, systemd, primo boot, aggiornamenti
7. [Stato attuale](07-stato-attuale.md) — cosa funziona davvero, incoerenze note, debito tecnico

## Convenzioni

Documentazione in italiano, codice e identificatori in inglese — stessa convenzione degli
altri repo dell'ecosistema (vedi [G2/README.md](../../README.md)). Quando un documento
descrive un comportamento non verificato su hardware reale, lo dichiara esplicitamente
invece di darlo per buono.
