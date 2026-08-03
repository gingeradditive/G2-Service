"""Schemi dei job asincroni (docs 02 — Operazioni lunghe)."""

from datetime import datetime
from enum import Enum
from typing import Any

from src.models.base import CamelModel


class JobStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobError(CamelModel):
    """Esito negativo di un job: non è un errore HTTP.

    Una password WiFi sbagliata non è un 4xx — l'operazione è stata accettata ed eseguita
    correttamente, ha solo dato esito negativo. Il `code` è specifico dell'operazione
    (`WIFI_AUTH_FAILED`, `CONFIG_DOWNLOAD_FAILED`, ...), non uno dei codici HTTP applicativi.
    """

    code: str
    message: str


class JobResponse(CamelModel):
    job_id: str
    type: str
    status: JobStatus
    started_at: datetime
    # I campi che valgono solo a job concluso restano presenti a `null` mentre è in corso: il
    # client ha così una forma sola da gestire invece di due.
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: JobError | None = None
