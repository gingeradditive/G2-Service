"""Implementazione mock di `UsbService`.

La logica è quella reale — leggere e copiare file funziona uguale su macOS — e cambia solo il
criterio di presenza: in sviluppo non c'è un mount da cercare, quindi la chiavetta "c'è" quando
esiste la cartella `media_dir` (`.devdata/media` di default). Crearla e cancellarla equivale a
inserire e togliere la chiavetta.
"""

from src.services.usb.real import FilesystemUsbService


class MockUsbService(FilesystemUsbService):
    def _is_mounted(self) -> bool:
        return self._media_dir.is_dir()
