# G2-Service

Servizio di sistema della Stampante G2 (stampante 3D a pellet Ginger, basata su
[Kalico](https://github.com/KalicoCrew/kalico)/[Moonraker](https://github.com/Arksine/moonraker)
su Raspberry Pi 4). Si occupa di tutto ciò che riguarda l'host e che Moonraker non copre:
connessione di rete (WiFi/Ethernet) e timezone di sistema.

Per il dettaglio su scope e architettura vedi la [documentazione](docs/README.md).

## Avvio

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## API

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- Health check: `GET /health`

> Stato attuale: è implementato **solo** l'endpoint di health. Tutto il resto (rete, timezone,
> configurazioni) è progettato nella documentazione ma non ancora scritto; quando lo sarà, gli
> endpoint staranno tutti sotto il prefisso `/service/`.
