# G2-Service

Backend API per la Stampante G2.

## Avvio

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

## API

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- Health check: `GET /health`
