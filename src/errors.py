"""Modello degli errori (docs 02 — Modello degli errori).

Sul filo esistono **due** forme, entrambe sotto la chiave `detail`:

1. errori di validazione — li genera FastAPI (`422`, una lista di problemi), e restano i suoi:
   riscriverli vorrebbe dire reimplementare Pydantic peggio;
2. errori applicativi — `AppError` e sottoclassi, tradotte dall'handler in
   `{"detail": {"code": "...", "message": "..."}}` con lo status della classe.

`JobFailure` è una terza cosa che *non* è un errore HTTP: è l'esito negativo previsto di
un'operazione asincrona e viaggia dentro il job, non nella risposta che lo ha avviato.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.models.errors import ErrorResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Errore applicativo con un codice stabile, leggibile dal client.

    Il codice è parte del contratto: GingerView ci si appoggia per decidere cosa mostrare, e
    non va cambiato con la stessa leggerezza di un messaggio.
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    default_message: str = "Errore interno"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidInputError(AppError):
    """Input sintatticamente valido ma non accettabile (es. un timezone inesistente)."""

    status_code = 400
    code = "INVALID_INPUT"
    default_message = "Input non valido"


class NotFoundError(AppError):
    """La risorsa indicata non esiste (una rete salvata, un job)."""

    status_code = 404
    code = "NOT_FOUND"
    default_message = "Risorsa non trovata"


class ConflictError(AppError):
    """Un'operazione dello stesso tipo è già in corso."""

    status_code = 409
    code = "CONFLICT"
    default_message = "Operazione già in corso"


class UsbNotMountedError(AppError):
    """Nessuna chiavetta montata (docs 07)."""

    status_code = 409
    code = "USB_NOT_MOUNTED"
    default_message = "Nessuna chiavetta USB inserita"


class TargetExistsError(AppError):
    """Il file di destinazione esiste già e la richiesta non dice cosa farne (docs 07)."""

    status_code = 409
    code = "FILE_EXISTS"
    default_message = "Esiste già un file con questo nome"


class UsbReadError(AppError):
    """La chiavetta non si lascia leggere, tipicamente perché è stata tolta (docs 07)."""

    status_code = 503
    code = "USB_READ_ERROR"
    default_message = "Lettura della chiavetta USB non riuscita"


class UpstreamUnavailableError(AppError):
    """Un servizio esterno non risponde (GitHub)."""

    status_code = 502
    code = "UPSTREAM_UNAVAILABLE"
    default_message = "Servizio esterno non raggiungibile"


class SystemToolUnavailableError(AppError):
    """Un comando di sistema manca o non risponde (NetworkManager giù, `nmcli` assente)."""

    status_code = 503
    code = "SYSTEM_TOOL_UNAVAILABLE"
    default_message = "Comando di sistema non disponibile"


class InternalError(AppError):
    """Tutto il resto, cioè un bug."""


class JobFailure(Exception):
    """Esito negativo *previsto* di un job asincrono.

    Non è un `AppError`: non diventa uno status HTTP. Sollevarla dentro la funzione di un job
    lo porta a `status: "failed"` con questo `code`. I codici sono quelli di docs 02:
    `WIFI_AUTH_FAILED`, `WIFI_NETWORK_NOT_FOUND`, `WIFI_TIMEOUT`, `CONFIG_*`.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def error_responses(*errors: type[AppError]) -> dict[int | str, dict[str, Any]]:
    """Dichiara in OpenAPI gli errori applicativi che una rotta può restituire."""
    return {
        error.status_code: {
            "model": ErrorResponse,
            "description": f"`{error.code}` — {error.default_message}",
        }
        for error in errors
    }


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # garantito da add_exception_handler
    if exc.status_code >= 500:
        logger.error("%s %s → %s: %s", request.method, request.url.path, exc.code, exc.message)
    else:
        logger.info("%s %s → %s: %s", request.method, request.url.path, exc.code, exc.message)
    return _error_response(exc.status_code, exc.code, exc.message)


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Un'eccezione non prevista è un bug: va nel log per intero, ma al client esce con la
    stessa forma di tutti gli altri errori e senza dettagli interni."""
    logger.exception("Errore non gestito su %s %s", request.method, request.url.path)
    return _error_response(
        InternalError.status_code, InternalError.code, InternalError.default_message
    )


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"detail": {"code": code, "message": message}}
    )
