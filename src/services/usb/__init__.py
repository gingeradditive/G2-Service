"""Servizio della chiavetta USB (docs 07)."""

from typing import Protocol

from src.models.usb import OnConflict, UsbDirectory, UsbStatus
from src.services.jobs import JobFunc

USB_IMPORT_JOB = "usb-import"


class UsbService(Protocol):
    async def status(self) -> UsbStatus: ...

    async def list_dir(self, path: str) -> UsbDirectory:
        """Solleva `UsbNotMountedError`, `NotFoundError`, `InvalidInputError`, `UsbReadError`."""
        ...

    async def prepare_import(self, source: str, dest_dir: str, on_conflict: OnConflict) -> JobFunc:
        """Valida la richiesta e restituisce la funzione del job che copia il file.

        Tutto quello che si può verificare subito si verifica qui, prima del `202`: è un errore
        HTTP e non l'esito di un job. In particolare il conflitto con `OnConflict.FAIL` diventa
        `409 FILE_EXISTS`, che è il modo in cui il client scopre di dover chiedere all'utente.
        """
        ...
