"""Servizio del fuso orario (docs 03 — Timezone)."""

import logging
import re
from pathlib import Path
from typing import Protocol

from src.errors import InvalidInputError
from src.models.timezone import TIMEZONE_PATTERN, TimezoneStatus

logger = logging.getLogger(__name__)

# Il database dei fusi di tzdata. Esiste sia su Linux sia su macOS, quindi la validazione è
# vera anche in sviluppo.
ZONEINFO_DIR = Path("/usr/share/zoneinfo")

_VALID_NAME = re.compile(TIMEZONE_PATTERN)


class TimezoneService(Protocol):
    async def status(self) -> TimezoneStatus:
        ...

    async def set_timezone(self, timezone: str) -> TimezoneStatus:
        """Solleva `InvalidInputError` (400) se il fuso non esiste su questa macchina."""
        ...


def ensure_timezone_exists(timezone: str) -> None:
    """Verifica che il fuso sia noto al sistema.

    Il controllo del formato è ripetuto qui e non lasciato solo allo schema: questa stringa
    diventa un percorso, e un `..` la trasformerebbe in una path traversal. Un servizio deve
    essere sicuro anche se domani lo chiama qualcuno che si è dimenticato di validare.
    """
    if not _VALID_NAME.match(timezone):
        raise InvalidInputError(f"Identificativo di fuso orario non valido: {timezone}")
    if not ZONEINFO_DIR.is_dir():
        # Senza tzdata non possiamo verificare niente: meglio lasciar decidere a
        # `timedatectl` che rifiutare qualsiasi fuso.
        logger.warning("%s non esiste: fuso orario non verificato", ZONEINFO_DIR)
        return
    if not (ZONEINFO_DIR / timezone).is_file():
        raise InvalidInputError(f"Fuso orario sconosciuto: {timezone}")
