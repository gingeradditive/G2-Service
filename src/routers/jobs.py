"""`GET /service/jobs/{jobId}` (docs 02 — Operazioni lunghe)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from src.dependencies import get_job_registry
from src.errors import NotFoundError, error_responses
from src.models.jobs import JobResponse
from src.services.jobs import JobRecord, JobRegistry

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    # `alias` tiene il segmento in camelCase come il resto del contratto, senza importare la
    # convenzione JSON dentro i nomi delle variabili Python.
    "/{jobId}",
    response_model=JobResponse,
    summary="Stato di un job asincrono",
    responses=error_responses(NotFoundError),
)
async def get_job(
    job_id: Annotated[
        str, Path(alias="jobId", description="Identificativo restituito dall'operazione")
    ],
    jobs: Annotated[JobRegistry, Depends(get_job_registry)],
) -> JobRecord:
    return jobs.get(job_id)
