# 06 — Matrice LED

> **Implementato e verificato**: `matrix/` è nel repository, le dipendenze sono in
> `requirements.txt`, `Scripts/install.sh` fa la sua parte, la prova sulla macchina vera è stata
> fatta e il percorso in `90_matrix.cfg` è stato aggiornato.

## Cos'è

Sulla stampante è montata una **matrice di LED MAX7219** collegata al Raspberry Pi via SPI. Serve
a mostrare messaggi durante la stampa ("HEATING", "LAYER 42", il nome del job), scritti dal gcode
tramite una macro Kalico.

Non è un display di sistema e non è un'interfaccia: è un canale di output che la stampante usa
per parlare a chi le sta davanti.

La matrice è **di serie su tutte le Stampanti G2**, ed è fatta di **8 moduli MAX7219 in cascata**
(il default `--cascaded 8` del programma): non è un accessorio opzionale, e su una macchina G2
l'assenza dell'hardware è un guasto, non una configurazione.

Cablaggio (rif. [pinout.xyz](https://pinout.xyz/pinout/pin24_gpio8/)):

| Matrice | Raspberry Pi |
|---|---|
| VCC | 5V (pin 2) |
| GND | GND (pin 6) |
| DIN | MOSI / GPIO10 (pin 19) |
| CS | CE0 / GPIO8 (pin 24) |
| CLK | SCLK / GPIO11 (pin 23) |

## Perché sta in G2-Service

La matrice è **hardware dell'host**, non della stampante: si pilota da GPIO/SPI con privilegi di
sistema, esattamente come rete e orologio. Kalico non la conosce e Moonraker non la espone —
è lo spazio che G2-Service occupa per definizione ([01 — Cos'è G2-Service](01-panoramica.md#cosè-g2-service)).

La ragione pratica pesa quanto quella di principio: così il codice della matrice **si aggiorna
da solo**. Il blocco `[update_manager G2-Service]` che è già su ogni macchina
([05](05-deploy-e-sviluppo.md#aggiornamento-tramite-lupdate_manager-di-moonraker)) fa `git pull`,
reinstalla le dipendenze e richiama `Scripts/install.sh`: la matrice entra in quel giro senza
aggiungere né un repository, né un blocco `update_manager`, né un secondo servizio da tenere in
piedi.

L'alternativa — un repo `G2-MatrixController` con un proprio `update_manager` — significherebbe un
secondo venv, un secondo install script e un secondo blocco da mantenere in `moonraker.conf`, per
due file.

## Cosa **non** è

- **Non è un'API.** Non c'è nessun endpoint `/service/matrix/…`, e il servizio FastAPI non viene
  coinvolto: chi scrive sulla matrice è Kalico, con un processo separato di pochi secondi di vita.
  Un endpoint HTTP si aggiungerà solo se un giorno servirà a GingerView, e oggi non serve.
- **Non è un servizio systemd.** Nessun demone: il processo lo lancia e lo termina la macro gcode.

## Struttura nel repository

```
G2-Service/
├── requirements.txt          include le dipendenze della matrice, con i marker (sotto)
└── matrix/
    ├── run_display.sh        il wrapper invocato da Kalico — eseguibile
    └── led_matrix_display.py il programma vero
```

`matrix/` sta **alla radice** e non sotto `src/`: `src/` è l'applicazione FastAPI, con la sua
struttura router/services/models ([02](02-architettura.md#organizzazione-del-codice)), e la
matrice non ne fa parte. Sono due eseguibili distinti che condividono solo il repository e il venv.

## Come lo chiama Kalico

Nelle configurazioni della stampante (`G2-Configs/90_matrix.cfg`, che vive in **G2-Printers** —
vedi [04](04-proposta-api-configurazioni.md)):

```ini
[gcode_shell_command LED_MSG]
command: /home/pi/G2-Service/matrix/run_display.sh
timeout: 10
verbose: True

[gcode_macro LED_MESSAGE]
gcode:
  {% if params.MSG is defined %}
    RUN_SHELL_COMMAND CMD=LED_MSG PARAMS="{params.MSG}"
  {% else %}
    RESPOND TYPE=error MSG="Parametro MSG mancante"
  {% endif %}
```

Dal gcode: `LED_MESSAGE MSG="STAMPA IN CORSO"`.

`[gcode_shell_command]` non richiede niente da installare: su **Kalico è nel core del firmware**,
a differenza di Klipper dove è l'estensione *G-Code Shell Command* da copiare a mano in
`klippy/extras/`. Nessuna dipendenza aggiuntiva sull'immagine, e niente che un aggiornamento di
Kalico possa portarsi via.

**Il percorso è assoluto e cablato nella configurazione**, quindi è un contratto fra due
repository: `/home/pi/G2-Service/matrix/run_display.sh`. È lo stesso `~/G2-Service` che
l'`update_manager` si aspetta, quindi non introduce un vincolo nuovo — ma spostare o rinominare
`matrix/` significa aggiornare anche `90_matrix.cfg` su G2-Printers.

### Perché un wrapper `.sh`

`gcode_shell_command` vuole un **singolo eseguibile** a cui accoda i `PARAMS`: non ci si può
infilare la riga `venv/bin/python led_matrix_display.py`. Il wrapper serve a quello, e a due
cose in più:

- **risolve i propri percorsi da sé**, a partire dalla posizione dello script, invece di cablare
  `/home/pi/…` come fa la versione attuale: il repository resta spostabile e lo script provabile
  da un checkout qualsiasi;
- **lancia in background** (`&`), perché il processo Python resta vivo (sotto) mentre
  `gcode_shell_command` ha un `timeout: 10` e il gcode non deve fermarsi ad aspettarlo.

### Perché il processo resta vivo

`luma.led_matrix` **spegne il display quando il processo termina**: un programma che scrive e
finisce lascia la matrice nera. Quindi il processo scrive il messaggio e poi dorme.

Ne segue il resto del meccanismo, che è già nel codice attuale e va mantenuto: un **PID file** in
`/tmp/led_matrix_display.pid` con cui ogni nuova invocazione termina la precedente. Senza, ogni
`LED_MESSAGE` lascerebbe indietro un processo che tiene occupato il bus SPI, e dopo dieci
messaggi ci sarebbero dieci processi a contendersi la matrice.

## Dipendenze e venv

**Un solo venv**, quello di G2-Service, con le dipendenze della matrice dentro
`requirements.txt` e **marker di ambiente** PEP 508:

```
luma.led_matrix>=1.7.0 ; sys_platform == "linux" and (platform_machine == "aarch64" or "arm" in platform_machine)
luma.core>=2.4.0 ; sys_platform == "linux" and (platform_machine == "aarch64" or "arm" in platform_machine)
spidev>=3.5 ; sys_platform == "linux" and (platform_machine == "aarch64" or "arm" in platform_machine)
RPi.GPIO>=0.7.0 ; sys_platform == "linux" and (platform_machine == "aarch64" or "arm" in platform_machine)
```

Il marker copre sia `aarch64` sia `armv7l` perché non è detto quale delle due immagini gira:
`"arm" in platform_machine` da solo **non** basterebbe, `aarch64` non contiene `arm`.

È l'unico modo per avere **entrambe** le cose che servono:

- **Moonraker aggiorna anche la matrice.** L'`update_manager` reinstalla `requirements` a ogni
  aggiornamento, ma installa *un solo* file di requirements in *un solo* venv, quelli dichiarati
  nel blocco. Dipendenze messe altrove (un `matrix/requirements.txt`, un `matrix/venv`) dovrebbe
  aggiornarle `install.sh`, che Moonraker richiama solo quando cambiano le dipendenze di sistema:
  un giro più fragile per nessun vantaggio.
- **Il repository resta installabile fuori dal Raspberry.** I marker escludono quei quattro
  pacchetti su macOS e su Linux x86, dove non compilano nemmeno: `pip install -r requirements.txt`
  continua a funzionare per lo sviluppo del servizio web, che con la matrice non c'entra.

Il prezzo è che il `requirements.txt` di un servizio HTTP contiene `RPi.GPIO`. È accettabile:
sono due eseguibili della stessa unità di deploy, e la riga con il marker si spiega da sé.

## Cosa aggiunge `install.sh`

Ai cinque passi già elencati in [05](05-deploy-e-sviluppo.md#scriptsinstallsh) se ne aggiungono
due, con la stessa regola di sempre — **idempotenti** e senza far fallire l'installazione su una
macchina che la matrice non ce l'ha:

6. **Abilitare SPI**, con `raspi-config nonint do_spi 0` se `raspi-config` c'è (è già così
   nell'install script attuale della matrice). Il comando è idempotente e vuole un riavvio per
   avere effetto, che nel percorso normale — immagine G2-OS costruita e poi avviata — arriva da
   solo. Se `raspi-config` manca, si **avvisa** e si va avanti: la matrice c'è su tutte le G2, ma
   `install.sh` deve poter girare anche su un checkout fatto a mano o su una macchina che non è
   una stampante, e la matrice non è una ragione per fermare l'installazione del servizio di rete.
7. **Garantire il bit di esecuzione** su `matrix/run_display.sh` (`chmod +x`). Git lo conserva,
   ma un checkout fatto male o un `umask` strano no, e il sintomo sarebbe un
   `gcode_shell_command` che fallisce senza dire perché.

Non serve niente per i **permessi**: lo script gira come l'utente di Kalico (`pi`), che su
Raspberry Pi OS è già nei gruppi `spi` e `gpio` — verificato sulla macchina vera. Se non fosse
così, il rimedio è nel modulo di G2-OS, non qui.

L'abilitazione di SPI potrebbe stare, in alternativa, nel modulo `69-G2-Service` di G2-OS
insieme alle `DEPS`. Sta in `install.sh` perché così vale anche per le macchine già in campo, che
il modulo non lo rieseguono mai più.

## Migrazione dalla macchina attuale

Sulla macchina di sviluppo esiste `~/G2-MatrixController` con un venv proprio, installato a mano.
Dopo il passaggio va **rimosso**, e `90_matrix.cfg` va aggiornato al nuovo percorso: se
restassero tutti e due, il vecchio continuerebbe a funzionare e nasconderebbe un aggiornamento
del nuovo che non ha mai avuto effetto.
