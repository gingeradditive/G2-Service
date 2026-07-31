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
- **Onboarding di rete via Access Point**: se all'avvio la macchina non trova nessuna rete
  WiFi nota né una connessione Ethernet, apre un proprio Access Point. Un utente che si
  connette all'AP vede un wizard di selezione/configurazione rete (esposto da GingerView, che
  chiama le API di setup di questo servizio); una volta configurata la rete la macchina si
  connette e chiude l'AP. Procedura standard per dispositivi IoT — non implementata in questa
  iterazione, vedi [03 — Proposta API](03-proposta-api-rete-timezone.md#5-onboarding-di-rete-futuro--non-ora).

## Cosa NON fa

Per evitare sovrapposizioni con il resto dello stack:

- non parla con la stampante via seriale/UART — è compito di Kalico;
- non gestisce file gcode, stampe, webcam, update manager — è compito di
  Moonraker/Crowsnest;
- non è un'interfaccia utente — quella è GingerView.

## Chi lo consuma

GingerView è il client di riferimento, ma oggi è ancora fermo al vecchio contratto: il suo
servizio
[`network-api.ts`](https://github.com/gingeradditive/GingerView/blob/main/src/lib/services/network-api.ts)
chiama endpoint `/api/wifi/*` in `snake_case`, e la pagina timezone simula
lettura/scrittura in locale in attesa di un vero `/api/timezone` (vedi la documentazione di
GingerView, `docs/04-moonraker.md#servizio-di-rete-non-moonraker`).

Il design deciso per G2-Service (vedi [03 — Proposta API](03-proposta-api-rete-timezone.md))
usa invece prefisso `/api/network/` e `camelCase` uniforme: **GingerView andrà aggiornato in
coordinamento** con l'implementazione di questi endpoint, non è compatibile "a costo zero"
con quanto cablato oggi nel client.

Nessuno di questi endpoint è ancora implementato in questa iterazione di G2-Service, che
espone solo `GET /health` (vedi [02 — Architettura](02-architettura.md#stato-attuale)).
