# 01 — Panoramica

## Contesto

La **Stampante G2** è una stampante 3D a pellet Ginger, basata su:

- **[Kalico](https://github.com/KalicoCrew/kalico)** — fork di Klipper, il firmware che
  pilota la macchina (motori, temperature, estrusione a pellet) via UART.
- **[Moonraker](https://github.com/Arksine/moonraker)** — API/websocket server che espone
  Kalico sulla rete (stato macchina, file gcode, macro, update manager).
- **GingerView** — interfaccia utente della macchina (SvelteKit, SPA statica), pensata per
  essere usata da smartphone. Sostituisce **integralmente**
  [Mainsail](https://github.com/mainsail-crew/mainsail): non viene installato affiancato, è
  l'unico frontend della Stampante G2.

Il tutto gira su **Raspberry Pi 4** con **[G2-OS](https://github.com/gingeradditive/G2-OS)**,
un fork di MainsailOS che preinstalla e configura Kalico, Moonraker, Crowsnest, Sonar e
Nginx, con GingerView al posto di Mainsail.

## Cos'è G2-Service

Moonraker espone tutto ciò che riguarda **la stampante** (Kalico), ma non ha visibilità né
privilegi su ciò che riguarda **l'host** (il Raspberry Pi in sé): connessione di rete,
orologio di sistema, e in generale la configurazione della macchina fisica su cui gira lo
stack.

G2-Service è il servizio che copre questo spazio: gira sullo stesso Raspberry Pi, con i
privilegi necessari per interagire con il sistema operativo (NetworkManager, `timedatectl`,
...), ed espone queste funzionalità via API HTTP.

È un progetto **indipendente** da Kalico/Moonraker: non li richiama e non dipende da loro
per funzionare — sono processi separati sullo stesso host, con responsabilità distinte.

## Ambito (scope)

### Ora

- **Connessione di rete (WiFi/Ethernet)**: scansione reti WiFi disponibili, connessione,
  disconnessione, stato degli adattatori (WiFi e cablato).
- **Timezone**: lettura e scrittura del fuso orario di sistema del Raspberry Pi. Non è una
  funzione della stampante e Moonraker non la espone in alcun modo.

### Futuro (non in questa iterazione)

- **Configurazioni stampante**: gestione avanzata di parametri macchina che oggi non hanno
  un posto dedicato. Ambito non ancora definito nel dettaglio — da riprendere in un secondo
  momento.

## Cosa NON fa

Per evitare sovrapposizioni con il resto dello stack:

- non parla con la stampante via seriale/UART — è compito di Kalico;
- non gestisce file gcode, stampe, webcam, update manager — è compito di
  Moonraker/Crowsnest;
- non è un'interfaccia utente — quella è GingerView.

## Chi lo consuma

GingerView è il client di riferimento. Il suo servizio
[`network-api.ts`](https://github.com/gingeradditive/GingerView/blob/main/src/lib/services/network-api.ts)
chiama già un set di endpoint `/api/wifi/*` per rete, e la pagina timezone è predisposta per
appoggiarsi a un endpoint `/api/timezone` non appena disponibile (nel frattempo simula
lettura/scrittura in locale — vedi la documentazione di GingerView,
`docs/04-moonraker.md#servizio-di-rete-non-moonraker`).

Questi contratti **non sono ancora implementati** in questa iterazione di G2-Service (che
espone solo `GET /health`, vedi [02 — Architettura](02-architettura.md#stato-attuale)), ma
sono un riferimento utile da tenere presente quando si progetteranno gli endpoint di rete e
timezone, per restare compatibili con l'unico consumer noto.
