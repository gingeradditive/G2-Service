"""Creazione dell'app e montaggio dei router sotto `/service`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src import __version__
from src.errors import register_exception_handlers
from src.routers import api_router
from src.services.container import build_services
from src.settings import API_PREFIX, Settings

logger = logging.getLogger(__name__)

DESCRIPTION = """
API di sistema dell'host della Stampante G2: rete, fuso orario e configurazione della macchina
fisica — tutto ciò di cui Moonraker non si occupa.

Convenzioni: ogni corpo JSON è in `camelCase`, gli errori applicativi hanno la forma
`{"detail": {"code", "message"}}`, e le operazioni che possono durare restituiscono `202` con
un job da interrogare su `/service/jobs/{jobId}`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "G2-Service %s avviato — mock=%s, etc=%s, printerData=%s",
        __version__,
        settings.mock,
        settings.etc_dir,
        settings.printer_data_dir,
    )
    yield
    await app.state.services.jobs.shutdown()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="G2-Service",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        # Swagger sta sotto il prefisso come tutto il resto: nginx instrada `/service/` verso
        # questo servizio e nient'altro, quindi una `/docs` alla radice non sarebbe
        # raggiungibile dalla macchina (docs 02 e 05).
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.state.settings = settings
    app.state.services = build_services(settings)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=API_PREFIX)
    return app


# uvicorn viene lanciato con `src.main:app`, sia da systemd sia da rundev.sh.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s"
)
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = app.state.settings
    uvicorn.run(app, host=settings.host, port=settings.port)
