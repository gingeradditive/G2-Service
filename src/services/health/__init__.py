"""Servizio di health: i check esposti da `GET /service/health`.

È anche l'esempio minimo della convenzione che vale per tutte le aree (docs 02): qui c'è il
`Protocol`, in `real.py` l'implementazione che parla col sistema e in `mock.py` quella che non
ne ha bisogno. Le implementazioni non ereditano dal `Protocol` — la conformità è strutturale,
è `build_services()` a dichiarare che restituisce un `HealthService`.
"""

from typing import Protocol

from src.models.health import HealthChecks
from src.settings import Settings


class HealthService(Protocol):
    async def checks(self) -> HealthChecks:
        """Nessun check solleva mai: una funzionalità non disponibile è `false`, non un
        errore. `/service/health` deve rispondere anche su una macchina messa male — è
        proprio lì che serve di più."""
        ...


def serial_configured(settings: Settings) -> bool:
    """Vero quando il seriale di fabbrica è stato impostato.

    Sta qui e non in una delle due implementazioni perché è la lettura di un file locale, non
    un comando di sistema: reale e mock si comportano allo stesso modo, cambia solo il
    percorso che arriva dalle `Settings`.
    """
    try:
        return bool(settings.serial_file.read_text().strip())
    except OSError:
        return False
