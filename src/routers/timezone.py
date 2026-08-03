"""`GET`/`POST /service/timezone` (docs 03 — Timezone)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from src.dependencies import get_timezone_service
from src.errors import InvalidInputError, SystemToolUnavailableError, error_responses
from src.models.timezone import TimezoneRequest, TimezoneStatus
from src.services.timezone import TimezoneService

router = APIRouter(tags=["timezone"])

TimezoneDep = Annotated[TimezoneService, Depends(get_timezone_service)]


@router.get(
    "/timezone",
    summary="Fuso orario di sistema",
    responses=error_responses(SystemToolUnavailableError),
)
async def get_timezone(timezone: TimezoneDep) -> TimezoneStatus:
    return await timezone.status()


@router.post(
    "/timezone",
    summary="Imposta il fuso orario di sistema",
    description=(
        "L'identificativo è quello IANA (`Europe/Rome`). Un fuso che questa macchina non "
        "conosce è `400 INVALID_INPUT`.\n\n"
        "L'elenco dei fusi validi non è esposto da questo servizio: GingerView lo genera già "
        "lato client da `zone.tab` di tzdata. `ntpSynchronized` è in sola lettura."
    ),
    responses=error_responses(InvalidInputError, SystemToolUnavailableError),
)
async def set_timezone(timezone: TimezoneDep, request: TimezoneRequest) -> TimezoneStatus:
    return await timezone.set_timezone(request.timezone)
