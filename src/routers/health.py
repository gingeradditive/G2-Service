"""`GET /service/health` (docs 03 — Health)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from src import __version__
from src.dependencies import get_health_service
from src.models.health import HealthResponse
from src.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Stato del servizio",
    description=(
        "Dice se G2-Service è presente, quale versione parla e quali funzionalità sono "
        "disponibili su questa macchina. `status` resta `ok` anche con dei check a `false`."
    ),
)
async def get_health(
    health: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse:
    return HealthResponse(version=__version__, checks=await health.checks())
