# 04 — Configurazione macchina

Questa è la parte meno ovvia del repository: `Configs/` e `printer.cfg` non sono
configurazione *del servizio* G2-Service, sono la **configurazione Klipper/Kalico della
stampante** — macro G-code, definizione di riscaldatori, estrusore a 3 zone, probe. Il
servizio Python non li legge né li scrive; li ospita e basta, perché questo repo è anche il
punto in cui viene versionata la config macchina condivisa tra le G2.

## File in `Configs/`

| File | Contenuto |
|---|---|
| `main.cfg` | Macro `START_PRINT` / `END_PRINT`: orchestrano riscaldamento piano, impostazione delle 3 zone dell'estrusore, leveling (KAMP o mesh globale), purge, e lo shutdown a fine stampa |
| `macro.cfg` | Macro di supporto `_GINGER_*` (bed, buzzer, cooler, extruder, feeder, probe, purge) richiamate da `main.cfg`, più le macro operatore `CHANGE_MATERIAL` e `CHANGE_NOZZLE` (wizard multi-step con prompt a schermo via `RESPOND TYPE=command`), override di `M104` e dei tool-change `T0`–`T3` |
| `mainsail.cfg` | Override di `PAUSE`/`RESUME`/`CANCEL_PRINT`: `PAUSE` salva le temperature correnti delle 3 zone in una variabile gcode, `RESUME` le ripristina prima di riprendere. Nonostante il nome, non ha a che fare con l'interfaccia Mainsail — è una collisione di nome con `mainsail-optimized.conf` (vedi sotto) |
| `mainsail-optimized.conf` | **Non è un file Klipper**: è un file di configurazione **nginx** (vhost con gzip, cache statica, proxy verso Moonraker su `:7125`). Il nome è fuorviante — non risulta referenziato da nessuno script del repo (né `install.sh` né gli script di setup Wi-Fi lo copiano in `/etc/nginx/`); sembra un artefatto lasciato da un tentativo di ottimizzazione nginx mai collegato al resto |
| `splash.png` | Immagine di avvio mostrata da `fbi` all'accensione (vedi il modulo `63-SplashScreen` in G2-OS) |

### Il "terzo estrusore" non è un terzo estrusore

Le macro (`_GINGER_EXTRUDER_SET_UP/MID/DOWN`) e la sezione `[extruder]`/`[extruder1]`/`[extruder2]`
di `printer.cfg` descrivono **tre zone riscaldate di un unico ugello** (banda alta/media/bassa),
non tre estrusori fisici indipendenti — stessa cosa osservata lato GingerView
(`GingerView/docs/07-stato-attuale.md`, sezione sulle 4 zone). Utile saperlo prima di leggere
il codice aspettandosi tre hotend separati.

## `printer.cfg`

Vive nella radice del repo ma **non è tracciato in git** (`.gitignore`: `printer.cfg` e
`Configs/printer.cfg`) — è specifico per ogni macchina fisica: contiene il percorso seriale
dell'MCU, la calibrazione del piano (`bed_mesh`, blocco `SAVE_CONFIG` generato da Klipper) e
lo z-offset del probe. Non va mai committato.

Include i file di `Configs/`:

```
[include G2-Service/mainsail.cfg]
[include kamp.cfg]
[include G2-Service/macro.cfg]
[include G2-Service/main.cfg]
```

**Da verificare**: questi include si aspettano una cartella `G2-Service/` dentro
`printer_data/config/`, ma `Scripts/install.sh` crea il symlink con un nome diverso
(`G2-Configs`, non `G2-Service`) — vedi
[07 — Stato attuale](07-stato-attuale.md#nome-del-symlink-config-diverso-da-quello-usato-negli-include).

Definisce inoltre cinematica cartesiana, i tre assi stepper (driver TMC5160 via SPI software),
l'estrusore a 3 zone, il probe servo-attuato, il sensore di runout del feeder, e i pin custom
per buzzer e camera LED — hardware specifico della G2.

## Come viene collegata alla macchina reale

`Scripts/install.sh` crea un symlink da `Configs/` verso la cartella di configurazione di
Moonraker/Klipper:

```bash
ln -sf "$(pwd)/Configs" ~/printer_data/config/G2-Configs
```

così Klipper (che legge `printer_data/config/printer.cfg`) può risolvere gli `[include ...]`
relativi. Il repository intero viene clonato in `/home/pi/G2-Service` dal modulo G2-OS che
lo installa (`modules/generic/69-G2-Service`).
