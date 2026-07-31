# 05 — Sviluppo

## Setup ambiente locale

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Richiede Python 3.8+ (usa f-string, type hint standard — nessuna sintassi più recente
osservata nel codice).

`requirements.txt` installa più di quanto il codice usi davvero: `sqlalchemy`, `alembic`,
`python-jose`, `passlib`, `structlog`, `rich` non sono importati da nessun file in `src/` —
sono coerenti con le funzionalità descritte nel `README.md` alla radice (database, JWT) ma
mai implementate. Non è un problema per far girare il servizio, solo peso extra
nell'installazione. Vedi [07 — Stato attuale](07-stato-attuale.md).

## Avviare il server

Tre modi, con comportamento leggermente diverso — vedi
[02 — Architettura](02-architettura.md#entry-point) per il dettaglio:

```bash
# Avvio semplice, nessun reload, porta 8080
python src/main.py

# Con auto-reload sui file in src/, bind su localhost, log debug — il più comodo in sviluppo
python debug.py

# Con opzioni esplicite (host/porta/workers) — non usato da nessuno script del repo
python src/server.py --host 0.0.0.0 --port 8080
```

Una volta avviato:
- API: `http://localhost:8080`
- Swagger UI: `http://localhost:8080/docs` (richiede internet per gli asset CDN)
- Doc offline: `http://localhost:8080/docs-offline`

## Sviluppare su macOS (o senza hardware Wi-Fi Raspberry Pi)

`NetworkManager`/`nmcli` non esistono su macOS, e `wlan0`/`wlan1` non sono interfacce reali.
Le chiamate a `_validate_wlan1()` falliscono, il codice cade nel fallback `iwlist` (fallisce
anche quello) e infine restituisce **dati Wi-Fi finti** (`TestNetwork_1`, `TestNetwork_2`,
`GuestNetwork` per `get_visible_networks`). Gli endpoint che richiedono uno stato reale
dell'adattatore (`get_wifi_status`, `connect`, ecc.) sollevano invece eccezione — vedi
`_validate_wlan1()` in `src/api/network.py`, che non ha un fallback mock per quei percorsi.

Utile per lavorare sull'interfaccia (GingerView) o sulla struttura delle risposte, non per
verificare il comportamento reale di connessione/scansione, che richiede una Raspberry Pi con
NetworkManager e le due interfacce Wi-Fi configurate come da [06 — Deploy](06-deploy.md).

## Test manuale del Wi-Fi

```bash
python test_wifi.py
```

Non è un test automatizzato (nessun framework, nessuna asserzione) — è uno script che chiama
`NetworkManager` e stampa i risultati a schermo, pensato per verificare a occhio che le
chiamate rispondano. Include anche stampa di chiavi (`status.get("connection")`,
`status.get("network")`) che **`get_wifi_status()` non restituisce più** nella struttura
attuale (che usa `adapter`/`ip`/`signal_info` — vedi
[03 — Wi-Fi e Access Point](03-wifi-e-access-point.md#get-apiwifistatus)): quei blocchi
stampano sempre vuoto, senza errore.

Non esiste una suite di test automatizzati (`pytest` è in `requirements.txt` ma non c'è
cartella `tests/` né file `test_*.py` con asserzioni reali).

## Linting

`black`, `flake8`, `mypy` sono in `requirements.txt` ma non risultano configurati (nessun
`pyproject.toml`, `setup.cfg` o `mypy.ini` nel repo) né richiamati da alcuno script — vanno
lanciati manualmente se servono:

```bash
black src/
flake8 src/
```
