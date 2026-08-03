"""Registro ed esecuzione dei job asincroni (docs 02 — Operazioni lunghe).

Le operazioni che possono durare non rispondono in modo sincrono: restituiscono `202` con un
identificativo, e il client interroga `GET /service/jobs/{jobId}` per sapere com'è andata. Il
motivo non è solo la durata — connettersi a una rete WiFi cambia l'indirizzo IP della macchina
e fa cadere la connessione HTTP su cui è arrivata la richiesta, quindi una risposta sincrona
non tornerebbe indietro comunque.

I job vivono **in memoria**: dopo un riavvio del servizio l'unica cosa che conta è lo stato
reale del sistema, che si legge dagli endpoint di stato.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from src.errors import AppError, ConflictError, JobFailure, NotFoundError
from src.models.jobs import JobError, JobStatus

logger = logging.getLogger(__name__)

JOB_TTL = timedelta(hours=1)

#: Una funzione di job: nessun argomento (le dipendenze si catturano alla partenza) e come
#: valore di ritorno il `result` da esporre al client. Per fallire con un esito previsto
#: solleva `JobFailure`.
JobFunc = Callable[[], Awaitable[dict[str, Any] | None]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class JobRecord:
    """Lo stato di un job. `JobResponse` ne è la proiezione HTTP."""

    job_id: str
    type: str
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: JobError | None = None

    @property
    def is_running(self) -> bool:
        return self.status is JobStatus.RUNNING

    def _finish(self, status: JobStatus) -> None:
        self.status = status
        self.finished_at = _now()

    def succeed(self, result: dict[str, Any] | None) -> None:
        self.result = result
        self._finish(JobStatus.SUCCEEDED)

    def fail(self, code: str, message: str) -> None:
        self.error = JobError(code=code, message=message)
        self._finish(JobStatus.FAILED)


@dataclass
class JobRegistry:
    """Registro in memoria dei job.

    Non serve nessun lock: tutto gira sull'event loop di uvicorn, e fra il controllo "ce n'è
    già uno di questo tipo?" e l'inserimento non c'è nessun `await` che possa cedere il
    controllo a un'altra richiesta.
    """

    ttl: timedelta = JOB_TTL
    _jobs: dict[str, JobRecord] = field(default_factory=dict, init=False, repr=False)
    _tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict, init=False, repr=False)

    def start(self, job_type: str, run: JobFunc) -> JobRecord:
        """Avvia un job e restituisce subito il suo record.

        Solleva `ConflictError` (409) se un job dello stesso tipo è già in corso: due
        connessioni WiFi contemporanee non hanno un esito sensato.

        Va chiamata dall'event loop, cioè da dentro un handler `async`.
        """
        self._purge()
        running = self._running_of_type(job_type)
        if running is not None:
            raise ConflictError(
                f"Un'operazione '{job_type}' è già in corso (job {running.job_id})"
            )

        record = JobRecord(
            job_id=uuid4().hex, type=job_type, status=JobStatus.RUNNING, started_at=_now()
        )
        self._jobs[record.job_id] = record
        task = asyncio.create_task(self._run(record, run), name=f"job:{job_type}")
        self._tasks[record.job_id] = task
        logger.info("Job %s avviato (%s)", record.job_id, job_type)
        return record

    def get(self, job_id: str) -> JobRecord:
        """Solleva `NotFoundError` (404) su un id sconosciuto **o scaduto**: dal punto di
        vista del client sono la stessa cosa, un job di cui non si sa più niente."""
        self._purge()
        record = self._jobs.get(job_id)
        if record is None:
            raise NotFoundError(f"Job sconosciuto o scaduto: {job_id}")
        return record

    async def shutdown(self) -> None:
        """Annulla i job ancora in corso allo spegnimento del servizio."""
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, record: JobRecord, run: JobFunc) -> None:
        try:
            result = await run()
        except JobFailure as exc:
            logger.info("Job %s fallito: %s — %s", record.job_id, exc.code, exc.message)
            record.fail(exc.code, exc.message)
        except AppError as exc:
            # Un errore applicativo sollevato dentro un job non ha nessuna risposta HTTP in
            # cui finire: diventa l'esito negativo del job, conservando il proprio codice.
            # Se NetworkManager cade a metà di una connessione, il job dice
            # `SYSTEM_TOOL_UNAVAILABLE` e non un generico errore interno.
            logger.warning("Job %s fallito: %s — %s", record.job_id, exc.code, exc.message)
            record.fail(exc.code, exc.message)
        except asyncio.CancelledError:
            # Succede allo spegnimento: il record resta coerente per chi lo leggesse ancora.
            record.fail("INTERNAL_ERROR", "Operazione interrotta")
            raise
        except Exception:
            # Un'eccezione non prevista dentro un job è un bug, ma non deve far cadere il
            # task in silenzio: finisce nel log per intero e nel job come INTERNAL_ERROR.
            logger.exception("Errore non gestito nel job %s (%s)", record.job_id, record.type)
            record.fail("INTERNAL_ERROR", "Errore interno durante l'operazione")
        else:
            logger.info("Job %s completato (%s)", record.job_id, record.type)
            record.succeed(result)
        finally:
            self._tasks.pop(record.job_id, None)

    def _running_of_type(self, job_type: str) -> JobRecord | None:
        return next(
            (job for job in self._jobs.values() if job.type == job_type and job.is_running),
            None,
        )

    def _purge(self) -> None:
        """Dimentica i job conclusi da più di `ttl`.

        La scadenza si misura dalla **fine**: un job ancora in corso non scade mai, altrimenti
        un'operazione lenta perderebbe il proprio risultato proprio mentre lo produce.
        """
        deadline = _now() - self.ttl
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job.finished_at is not None and job.finished_at < deadline
        ]
        for job_id in expired:
            del self._jobs[job_id]
