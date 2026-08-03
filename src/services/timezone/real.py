"""Implementazione reale di `TimezoneService`, sopra `timedatectl`.

Si legge da `timedatectl show` e non da `timedatectl status`: il primo è la forma pensata per
essere interpretata da un programma — `Chiave=valore`, nomi stabili, niente traduzioni — il
secondo è impaginato per una persona e cambia con la lingua di sistema.
"""

import logging

from src.errors import InternalError, InvalidInputError, SystemToolUnavailableError
from src.models.timezone import TimezoneStatus
from src.services.system import run_command
from src.services.timezone import ensure_timezone_exists
from src.settings import Settings

logger = logging.getLogger(__name__)

TIMEDATECTL = "timedatectl"

# I messaggi d'errore di `timedatectl`, invece, sono tradotti: `LC_ALL=C` per poterli leggere.
_C_LOCALE = {"LC_ALL": "C", "LANG": "C"}

# Marcatori di un fuso rifiutato dal comando: capita solo se tzdata non c'era e la verifica
# preventiva è stata saltata.
_INVALID_MARKERS = ("invalid time zone", "not a valid", "no such file")


class TimedatectlTimezoneService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def status(self) -> TimezoneStatus:
        properties = await self._show()
        timezone = properties.get("Timezone")
        if not timezone:
            # Non c'è un valore di ripiego onesto: dire "UTC" quando non lo sappiamo sarebbe
            # una risposta su cui l'utente potrebbe agire.
            raise SystemToolUnavailableError("timedatectl non riporta il fuso orario")
        return TimezoneStatus(
            timezone=timezone,
            ntp_synchronized=properties.get("NTPSynchronized", "").lower() == "yes",
        )

    async def set_timezone(self, timezone: str) -> TimezoneStatus:
        ensure_timezone_exists(timezone)
        result = await run_command(
            [TIMEDATECTL, "set-timezone", timezone], env=_C_LOCALE
        )
        if not result.ok:
            raise _set_failure(timezone, result.stderr)
        logger.info("Fuso orario impostato a %s", timezone)
        return await self.status()

    async def _show(self) -> dict[str, str]:
        result = await run_command([TIMEDATECTL, "show"], env=_C_LOCALE)
        if not result.ok:
            raise SystemToolUnavailableError(
                f"timedatectl non risponde: {result.stderr.strip() or 'errore sconosciuto'}"
            )
        return parse_show(result.stdout)


def parse_show(stdout: str) -> dict[str, str]:
    """Legge l'output `Chiave=valore` di `timedatectl show`."""
    properties = {}
    for line in stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            properties[key.strip()] = value.strip()
    return properties


def _set_failure(timezone: str, stderr: str) -> Exception:
    message = stderr.strip() or "errore sconosciuto"
    if any(marker in message.lower() for marker in _INVALID_MARKERS):
        return InvalidInputError(f"Fuso orario sconosciuto: {timezone}")
    return InternalError(f"Fuso orario non impostato: {message}")
