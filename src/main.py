from fastapi import FastAPI

app = FastAPI(title="G2-Service")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
