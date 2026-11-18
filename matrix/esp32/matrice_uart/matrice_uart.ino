// Firmware della matrice LED per ESP32-C3 supermini (vedi docs/06-matrice-led.md).
//
// Il Raspberry manda l'immagine già disegnata su una seriale lenta, un solo filo lungo; l'ESP
// sta accanto alla matrice e la pilota con fili di pochi centimetri. Serve dove il cavo verso
// la matrice è troppo lungo e disturbato per lo SPI diretto dal Raspberry.
//
// Frame (9600 8N1, su GPIO20):
//   A5 5A | moduli | intensità 0-15 | 8 righe x moduli byte | CRC-8 (poly 0x07)
// Riga per riga, un byte per modulo; bit b = colonna b del modulo, da sinistra.
//
// Robustezza:
//   - un frame con CRC sbagliato viene scartato: resta l'ultimo messaggio valido;
//   - la matrice viene riscritta da capo (configurazione compresa) ogni secondo, così un
//     disturbo che sporca i registri dei MAX7219 sparisce da solo;
//   - l'ultimo frame valido è salvato in flash e rimostrato dopo un riavvio. Si scrive solo
//     quando il contenuto cambia: il Raspberry ripete lo stesso frame ogni 5 secondi.

#include <Preferences.h>

const uint8_t PIN_CLK = 5, PIN_DIN = 6, PIN_CS = 7, PIN_RX = 20;
const uint8_t MAX_MODULI = 16;
const uint32_t REFRESH_MS = 1000;
const uint32_t TIMEOUT_BYTE_MS = 100;  // pausa oltre la quale un frame a metà si butta
const uint16_t MEZZO_CLOCK_US = 50;    // circa 10 kHz: i fili sono corti, la velocità non conta

Preferences flash;

uint8_t moduli = 8;
uint8_t intensita = 1;
uint8_t schermo[8 * MAX_MODULI];  // [riga * moduli + modulo]

// ---- MAX7219 -------------------------------------------------------------------------------

void shiftByte(uint8_t v) {
  for (int8_t i = 7; i >= 0; i--) {
    digitalWrite(PIN_DIN, (v >> i) & 1);
    delayMicroseconds(MEZZO_CLOCK_US);
    digitalWrite(PIN_CLK, HIGH);
    delayMicroseconds(MEZZO_CLOCK_US);
    digitalWrite(PIN_CLK, LOW);
  }
}

// Un registro per tutti i moduli: valori[m] per il modulo m, oppure lo stesso valore a tutti.
void scrivi(uint8_t reg, const uint8_t *valori, uint8_t valoreUnico) {
  digitalWrite(PIN_CS, LOW);
  for (int8_t m = moduli - 1; m >= 0; m--) {  // il primo dato shiftato va al modulo più lontano
    shiftByte(reg);
    shiftByte(valori ? valori[m] : valoreUnico);
  }
  digitalWrite(PIN_CS, HIGH);
  delayMicroseconds(MEZZO_CLOCK_US);
}

void aggiornaMatrice() {
  scrivi(0x0F, nullptr, 0);          // display test off
  scrivi(0x09, nullptr, 0);          // decode off
  scrivi(0x0B, nullptr, 7);          // scan limit: 8 righe
  scrivi(0x0A, nullptr, intensita);  // intensità
  uint8_t valori[MAX_MODULI];
  for (uint8_t d = 0; d < 8; d++) {
    // Stessa mappatura di luma con block_orientation=-90: il registro d contiene la riga 7-d.
    for (uint8_t m = 0; m < moduli; m++) valori[m] = schermo[(7 - d) * moduli + m];
    scrivi(d + 1, valori, 0);
  }
  scrivi(0x0C, nullptr, 1);          // esci da shutdown
}

// ---- Ricezione -----------------------------------------------------------------------------

uint8_t crc8(const uint8_t *dati, size_t n) {
  uint8_t crc = 0;
  for (size_t i = 0; i < n; i++) {
    crc ^= dati[i];
    for (uint8_t b = 0; b < 8; b++) crc = (crc & 0x80) ? (crc << 1) ^ 0x07 : crc << 1;
  }
  return crc;
}

uint8_t buf[2 + 8 * MAX_MODULI + 1];  // moduli, intensità, bitmap, crc
size_t pos = 0;      // byte del corpo ricevuti
uint8_t header = 0;  // 0: aspetto A5, 1: aspetto 5A, 2: dentro il frame
uint32_t ultimoByte = 0;

void applicaFrame(const uint8_t *corpo, size_t lunghezza, bool salva) {
  moduli = corpo[0];
  intensita = corpo[1] & 0x0F;
  memcpy(schermo, corpo + 2, 8 * moduli);
  if (salva) {
    uint8_t salvato[sizeof(buf)];
    size_t n = flash.getBytes("frame", salvato, sizeof(salvato));
    if (n != lunghezza || memcmp(salvato, corpo, lunghezza) != 0) {
      flash.putBytes("frame", corpo, lunghezza);
      Serial.println("frame salvato in flash");
    }
  }
}

// Ritorna true quando è arrivato un frame valido.
bool ricevi() {
  bool nuovo = false;
  while (Serial1.available()) {
    uint8_t c = Serial1.read();
    uint32_t ora = millis();
    if (header == 2 && ora - ultimoByte > TIMEOUT_BYTE_MS) header = 0;
    ultimoByte = ora;

    if (header == 0) { header = (c == 0xA5) ? 1 : 0; continue; }
    if (header == 1) { header = (c == 0x5A) ? 2 : (c == 0xA5 ? 1 : 0); pos = 0; continue; }

    buf[pos++] = c;
    if (pos == 1 && (buf[0] == 0 || buf[0] > MAX_MODULI)) { header = 0; continue; }
    if (pos >= 2) {
      size_t corpo = 2 + 8 * buf[0];
      if (pos == corpo + 1) {
        header = 0;
        if (crc8(buf, corpo) == buf[corpo]) {
          applicaFrame(buf, corpo, true);
          nuovo = true;
        } else {
          Serial.println("frame scartato: CRC errato");
        }
      }
    }
  }
  return nuovo;
}

// ---- Main ----------------------------------------------------------------------------------

uint32_t ultimoRefresh = 0;

void setup() {
  pinMode(PIN_CLK, OUTPUT);
  pinMode(PIN_DIN, OUTPUT);
  pinMode(PIN_CS, OUTPUT);
  digitalWrite(PIN_CS, HIGH);
  digitalWrite(PIN_CLK, LOW);

  Serial.begin(115200);  // USB, solo per debug
  Serial1.setRxBufferSize(1024);
  Serial1.begin(9600, SERIAL_8N1, PIN_RX, -1);

  memset(schermo, 0, sizeof(schermo));
  flash.begin("matrice", false);
  size_t n = flash.getBytes("frame", buf, sizeof(buf));
  if (n >= 2 && buf[0] > 0 && buf[0] <= MAX_MODULI && n == 2 + 8u * buf[0]) {
    applicaFrame(buf, n, false);
    Serial.println("frame ripreso dalla flash");
  }
  aggiornaMatrice();
}

void loop() {
  bool nuovo = ricevi();
  if (nuovo || millis() - ultimoRefresh >= REFRESH_MS) {
    aggiornaMatrice();
    ultimoRefresh = millis();
  }
}
