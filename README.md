# G2-Service

Backend API server per la Stampante G2 - Sistema di gestione avanzata della macchina

## Panoramica

G2-Service è il sistema di backend della Stampante G2 che fornisce un'API RESTful per la gestione delle impostazioni avanzate della macchina, aggiornamenti firmware e altre funzionalità specifiche del sistema.

## Funzionalità Principali

- **Gestione Impostazioni Macchina**: Configurazione avanzata dei parametri di stampa
- **Aggiornamenti Firmware**: Gestione sicura degli aggiornamenti del sistema
- **Monitoraggio Stato**: Controllo in tempo dello stato della stampante
- **API RESTful**: Interfaccia completa per client esterni
- **Configurazioni Personalizzate**: Supporto per profili di stampa personalizzati

## Architettura

```
G2-Service/
├── src/                    # Codice sorgente principale
├── Configs/                # File di configurazione
├── Scripts/                # Script di installazione e manutenzione
├── tests/                  # Test unitari e di integrazione
├── docs/                   # Documentazione API
└── requirements.txt        # Dipendenze Python
```

## Requisiti di Sistema

- Python 3.8+
- Sistema operativo compatibile con la stampante G2
- Accesso alle periferiche della stampante
- Connessione di rete per aggiornamenti

## Installazione

### Prerequisiti

Assicurarsi di avere Python 3.8 o superiore installato:

```bash
python --version
```

### Installazione Rapida

1. Clonare il repository:
```bash
git clone <repository-url>
cd G2-Service
```

2. Creare ambiente virtuale:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows
```

3. Installare le dipendenze:
```bash
pip install -r requirements.txt
```

4. Eseguire lo script di installazione:
```bash
chmod +x Scripts/install.sh
./Scripts/install.sh
```

## Avvio del Servizio

### Sviluppo

```bash
python src/main.py
```

### Produzione

```bash
python src/server.py --host 0.0.0.0 --port 8080
```

## Configurazione

Il file di configurazione principale si trova in `Configs/printer.cfg`. Esempio di configurazione:

```ini
[server]
host = localhost
port = 8080
debug = false

[printer]
model = G2
serial_port = /dev/ttyUSB0
baud_rate = 115200

[updates]
auto_check = true
update_interval = 86400
```

## API Documentation

### Endpoints Principali

#### Gestione Impostazioni
- `GET /api/settings` - Ottieni tutte le impostazioni
- `PUT /api/settings/{param}` - Aggiorna un parametro specifico
- `POST /api/settings/reset` - Ripristina impostazioni di fabbrica

#### Aggiornamenti
- `GET /api/updates/check` - Controlla aggiornamenti disponibili
- `POST /api/updates/install` - Installa aggiornamento
- `GET /api/updates/status` - Stato aggiornamento corrente

#### Stato Macchina
- `GET /api/status` - Stato completo della stampante
- `GET /api/status/health` - Controllo salute sistema
- `POST /api/status/reboot` - Riavvio sistema

### Autenticazione

L'API utilizza token JWT per l'autenticazione:

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8080/api/status
```

## Sviluppo

### Struttura del Codice

- `src/api/` - Rotte API e handler
- `src/core/` - Logica di business principale
- `src/models/` - Modelli dati e database
- `src/services/` - Servizi esterni e integrazioni
- `src/utils/` - Utilità e helper functions

### Test

Eseguire i test:

```bash
python -m pytest tests/
```

Test con coverage:

```bash
python -m pytest --cov=src tests/
```

### Linting

```bash
flake8 src/
black src/
```

## Manutenzione

### Backup Configurazioni

```bash
cp Configs/printer.cfg Configs/printer.cfg.backup
```

### Logs

I log di sistema si trovano in:
- `logs/g2-service.log` - Log principale
- `logs/updates.log` - Log aggiornamenti
- `logs/errors.log` - Log errori

### Troubleshooting

**Servizio non si avvia:**
1. Verificare le dipendenze con `pip list`
2. Controllare i permessi sui file di configurazione
3. Verificare la disponibilità delle porte

**Problemi di connessione stampante:**
1. Controllare il collegamento seriale/USB
2. Verificare i permessi sulle periferiche
3. Testare con `python -m serial.tools.list_ports`

## Sicurezza

- L'API è protetta da autenticazione JWT
- Le comunicazioni sensibili sono crittografate
- Gli aggiornamenti vengono verificati prima dell'installazione
- Accesso limitato alle periferiche di sistema

## Licenza

Questo progetto è protetto da licenza proprietaria. Contattare il produttore per informazioni sull'utilizzo.

## Supporto

Per assistenza tecnica:
- Email: support@ginger-print.com
- Documentazione: [Link alla documentazione interna]
- Issue Tracker: [Link al sistema di tracking]

## Version History

- **v1.0.0** - Release iniziale con funzionalità base
- **v1.1.0** - Aggiunto supporto aggiornamenti automatici
- **v1.2.0** - Migliorata sicurezza e performance

---

**G2-Service** © 2024 Ginger Printing Systems. Tutti i diritti riservati.
