"""`/service/usb` (docs 07 — Chiavetta USB)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.dependencies import get_job_registry, get_usb_service
from src.errors import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    TargetExistsError,
    UsbNotMountedError,
    UsbReadError,
    error_responses,
)
from src.models.jobs import JobResponse
from src.models.usb import PATH_MAX_LENGTH, UsbDirectory, UsbImportRequest, UsbStatus
from src.services.jobs import JobRecord, JobRegistry
from src.services.usb import USB_IMPORT_JOB, UsbService

router = APIRouter(prefix="/usb", tags=["usb"])

UsbDep = Annotated[UsbService, Depends(get_usb_service)]
JobsDep = Annotated[JobRegistry, Depends(get_job_registry)]


@router.get("", summary="Presenza della chiavetta USB")
async def get_usb_status(usb: UsbDep) -> UsbStatus:
    return await usb.status()


@router.get(
    "/files",
    summary="Contenuto di una cartella della chiavetta",
    description=(
        "Solo cartelle e file stampabili (`.gcode`); nascosti e cartelle di sistema esclusi."
    ),
    responses=error_responses(UsbNotMountedError, NotFoundError, InvalidInputError, UsbReadError),
)
async def list_usb_files(
    usb: UsbDep,
    path: Annotated[
        str, Query(max_length=PATH_MAX_LENGTH, description="Relativo alla chiavetta")
    ] = "",
) -> UsbDirectory:
    return await usb.list_dir(path)


@router.post(
    "/import",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobResponse,
    summary="Importa un file dalla chiavetta in `gcodes`",
    description=(
        "Con `onConflict: fail` (default) un file già presente in `destDir` è `409 "
        "FILE_EXISTS` subito, senza avviare il job: il client chiede all'utente e ripete con "
        "`overwrite` o `rename`. Il job (`usb-import`) restituisce `{filename, path}` con il "
        "nome finale."
    ),
    # `FILE_EXISTS`, `USB_NOT_MOUNTED` e `CONFLICT` sono tutti 409: OpenAPI ne mostra uno solo,
    # i codici completi stanno in docs 07.
    responses=error_responses(
        TargetExistsError, NotFoundError, InvalidInputError, UsbNotMountedError, ConflictError
    ),
)
async def import_usb_file(usb: UsbDep, jobs: JobsDep, request: UsbImportRequest) -> JobRecord:
    run = await usb.prepare_import(request.source, request.dest_dir, request.on_conflict)
    return jobs.start(USB_IMPORT_JOB, run)
