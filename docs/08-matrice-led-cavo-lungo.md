# 08 — Matrice LED su cavo lungo: prove e soluzione

> Resoconto delle prove del **2026-11-09** sulla G2 di prova (`192.168.1.149`), preparata per la
> fiera. Serve a decidere come cablare la matrice in produzione. Il funzionamento dello script è
> in [06 — Matrice LED](06-matrice-led.md).

## Il problema

Sulla G2 il Raspberry Pi è nel pannello e la matrice (8 moduli MAX7219 in cascata) è a circa
**5 m di cavo**. Con lo SPI diretto dal Raspberry la matrice **resta tutta rossa**: tutti i LED
accesi, nessun messaggio leggibile.

"Tutta rossa" vuol dire che i MAX7219 ricevono comandi sbagliati (tipicamente finiscono in
*display test* o a intensità massima). È un problema di **segnale**, non di software né di
alimentazione.

## Cosa abbiamo provato

| # | Prova | Risultato |
|---|---|---|
| 1 | Clock SPI da 8 MHz (default di luma) a 500 kHz | Ancora tutta rossa |
| 2 | Verifica lato Raspberry: SPI attivo, pin in ALT0, permessi, processo vivo | Tutto a posto: il software non c'entra |
| 3 | **Telaio messo a terra** | Funziona, ma solo finché il cavo non viene mosso |
| 4 | Riavvio, cavo chiuso e spostato | Di nuovo rossa. Anche riscrivendo il messaggio a macchina ferma (motori, ventole, riscaldatori spenti) |
| 5 | **Arduino Nano nel pannello** (segnali a 5 V, clock bit-bang 2 kHz, riscrittura ogni secondo), stesso cavo | A stampante spenta la matrice si legge; quando si accende il resto della macchina **sfarfalla** |
| 6 | **ESP32-C3 accanto alla matrice**, collegato al Raspberry da **una sola linea seriale** a 9600 baud | **Funziona** |

## Cause

Le prove indicano tre cause che si sommano:

1. **Diafonia nel cavo.** CLK, DIN e CS corrono affiancati per 5 m, senza masse in mezzo e senza
   schermo: ogni fronte di CLK induce impulsi su CS e DIN. Lo dimostra la prova 4, dove è bastato
   muovere il cavo per cambiare il risultato.
2. **Disturbi della macchina (EMI).** Quando si accende l'elettronica di potenza (alimentatori,
   driver dei motori) gli impulsi raccolti dal cavo bastano a far latchare dati sbagliati ai
   MAX7219 (prova 5). La messa a terra del telaio li riduce (prova 3).
3. **Livelli logici al limite.** Il Raspberry esce a 3,3 V, mentre un MAX7219 alimentato a 5 V
   vuole almeno circa 3,5 V per leggere un "1". Su un cavo lungo il margine sparisce.

**Abbassare il clock non basta**: aiuta contro i rimbalzi, ma un impulso su CS fa latchare dati
sbagliati qualunque sia la velocità. Anche portare i segnali a 5 V (Nano nel pannello) non basta,
finché tre segnali SPI viaggiano sui 5 m.

## Soluzione adottata (macchina della fiera)

**Il microcontrollore sta accanto alla matrice; sul cavo lungo passa un solo segnale lento.**

```
Raspberry Pi ── GPIO14 TX, 9600 baud ── 5 m ── ESP32-C3 ── fili di pochi cm ── matrice MAX7219
```

- I segnali veloci (CLK, DIN, CS) sono lunghi pochi centimetri, quindi non raccolgono disturbi.
- Sul cavo c'è una sola linea seriale lenta, e ogni frame ha un **CRC-8**: un frame rovinato
  viene scartato e la matrice tiene l'ultimo messaggio valido.
- L'ESP **riscrive tutta la matrice ogni secondo**, configurazione compresa: se un disturbo
  sporca comunque i registri, sparisce entro un secondo.
- L'ESP **salva l'ultimo frame in flash** e lo rimostra dopo un riavvio.
- L'ESP pilota la matrice a 3,3 V. Sui fili corti funziona. Restano da verificare tempi lunghi e
  matrici diverse (vedi [Da verificare](#da-verificare)).

### Collegamenti

**Lato pannello**

| Da | A |
|---|---|
| Raspberry pin 8 (GPIO14 TX) | cavo, filo 3 (bianco, ex DIN) |
| Alimentatore 5 V (quello da 7 A che alimenta anche il Raspberry) | cavo, filo 1 (VCC) |
| GND alimentatore | cavo, filo 2 (GND) |

**Lato matrice**

| Da | A |
|---|---|
| Filo 3 (TX) | resistenza 1 kΩ → ESP32-C3 GPIO20 (RX) |
| Filo 1 (5 V) | ESP32-C3 pin 5V e VCC della matrice |
| Filo 2 (GND) | ESP32-C3 GND e GND della matrice |
| ESP32-C3 GPIO5 | CLK della matrice |
| ESP32-C3 GPIO6 | DIN della matrice |
| ESP32-C3 GPIO7 | CS della matrice |

Fili del cavo igus **prima** della modifica, per riferimento: 1 VCC, 2 GND, 3 DIN, 4 CS,
giallo-verde CLK.

> **Da completare:** come sono stati usati sulla macchina della fiera i fili 4 e giallo-verde
> dopo la modifica (liberi, oppure messi a GND).

### Software

| Cosa | Dove |
|---|---|
| Firmware ESP32-C3 | `matrix/esp32/matrice_uart/matrice_uart.ino` |
| Script lato Raspberry | `matrix/led_matrix_display.py --uart /dev/serial0` |
| Scelta del backend per macchina | `/etc/g2/matrix.env` con `MATRIX_ARGS="--uart /dev/serial0"` |

- Senza `/etc/g2/matrix.env` lo script usa lo SPI diretto come prima: le altre G2 non cambiano.
- La configurazione Kalico (`90_matrix.cfg`) **non cambia**: `LED_MESSAGE` chiama sempre
  `run_display.sh`, che legge `matrix.env`.
- Sul Raspberry non serve nessuna libreria nuova: la seriale si apre con `termios`, senza pyserial.
- `/dev/serial0` (ttyAMA0) è libera: nessuna console sopra (`cmdline.txt` ha solo `console=tty1`)
  e Kalico usa solo dispositivi USB. `enable_uart=1` e `dtoverlay=disable-bt` sono già nella
  `config.txt` di G2-OS.
- Il processo sul Raspberry **rimanda il frame ogni 5 secondi**: copre un reset dell'ESP o un
  frame perso.

Caricare il firmware dal Mac, con l'ESP collegato via USB-C:

```sh
arduino-cli compile --fqbn esp32:esp32:esp32c3:CDCOnBoot=cdc matrix/esp32/matrice_uart
arduino-cli upload -p /dev/cu.usbmodem101 --fqbn esp32:esp32:esp32c3:CDCOnBoot=cdc matrix/esp32/matrice_uart
```

Il primo upload a volte fallisce: basta ripeterlo. Sulla USB l'ESP scrive messaggi di debug a
115200 baud (frame salvato, frame scartato per CRC).

Formato del frame (9600 8N1):

```
A5 5A | moduli | intensità 0-15 | 8 righe × moduli byte | CRC-8 (poly 0x07, init 0)
```

Riga per riga, un byte per modulo; bit b = colonna b del modulo, da sinistra. L'orientamento dei
moduli è lo stesso di luma con `block_orientation=-90`: il registro digit *d* contiene la riga 7−*d*.

## Indicazioni per la produzione

1. **Microcontrollore accanto alla matrice, seriale sul cavo lungo.** È l'unica configurazione
   che ha retto a macchina accesa. Va prevista nel progetto meccanico fin dall'inizio: alla
   fiera l'ESP32-C3 supermini è stato saldato direttamente sulla matrice perché non c'era spazio.
2. **Telaio a terra.** Ha fatto la differenza anche con lo SPI diretto: va garantito e verificato
   in collaudo.
3. **Cavo:** con la seriale bastano 3 conduttori (5 V, GND, TX). Se ce ne sono di più, usarli come
   GND in parallelo. Va bene anche un cavo schermato, con la calza a massa **solo lato pannello**.
4. **Alimentazione dal pannello sullo stesso cavo.** Nel caso peggiore (tutti i LED accesi alla
   massima intensità) la matrice assorbe circa 2,5 A: su 5 m di filo da 0,5 mm² ai moduli
   arrivano circa 4,1 V, al limite dei 4 V minimi dei MAX7219. Per la produzione:
   - fili da 0,75–1 mm² per 5 V e GND, oppure più conduttori in parallelo;
   - un **fusibile da circa 3 A** sul 5 V lato pannello: l'alimentatore da 7 A brucerebbe un filo
     da 0,5 mm² in caso di corto;
   - in alternativa portare 24 V sul cavo e usare uno step-down 24→5 V sulla matrice (circa
     0,55 A sul cavo invece di 2,5 A).
5. **Mai usare il giallo-verde per un segnale**: per norma è la terra di protezione.
6. **Non spegnere togliendo corrente subito dopo un aggiornamento.** Durante le prove un file
   appena copiato è finito rovinato e `matrix.env` vuoto, perché la stampante è stata spenta
   prima che Linux li salvasse sulla SD.

Soluzioni **scartate**:

- **SPI diretto dal Raspberry su 5 m**: non regge, anche a 500 kHz.
- **Nano (o un traslatore di livello 74HCT245) nel pannello, SPI a 5 V sul cavo**: migliora, ma
  sfarfalla a macchina accesa.
- **USB sul cavo da 5 m fino a un micro accanto alla matrice**: non provata. La USB vuole una
  coppia intrecciata e schermata, quindi è a rischio con questi disturbi.
- **Filtri RC (1–100 nF verso GND) sugli ingressi della matrice**: non provati, perché scomodi da
  montare. Sarebbero il passo successivo se servisse ancora lo SPI sul cavo lungo.

## Da verificare

- Tenuta per ore a macchina in stampa (motori e riscaldatori attivi), non solo accesa.
- L'ESP pilota i MAX7219 a 3,3 V, sotto la soglia nominale di circa 3,5 V. Sui fili corti
  funziona, ma con un altro lotto di moduli potrebbe non bastare. In produzione si può valutare
  un micro a 5 V, oppure un buffer 74HCT sulla scheda della matrice.
- Il codice è sul branch `feat/matrice-uart-esp32` di G2-Service, non ancora su main. Sulla
  macchina della fiera i file sono copiati a mano.
