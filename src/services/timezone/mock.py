"""Implementazione mock di `TimezoneService`.

Tiene lo stato come il mock di rete: impostare un fuso cambia davvero quello che risponde il
`GET` successivo. La validazione invece **non** è finta — `/usr/share/zoneinfo` esiste anche
su macOS — quindi un identificativo sbagliato dà `400 INVALID_INPUT` in sviluppo come sulla
macchina vera.
"""

from src.models.timezone import TimezoneStatus
from src.services.timezone import ensure_timezone_exists
from src.settings import Settings

_DEFAULT_TIMEZONE = "Europe/Rome"


class MockTimezoneService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._timezone = _DEFAULT_TIMEZONE
        # Su una macchina vera con la rete NTP è sincronizzato: è il caso normale.
        self._ntp_synchronized = True

    async def status(self) -> TimezoneStatus:
        return TimezoneStatus(
            timezone=self._timezone, ntp_synchronized=self._ntp_synchronized
        )

    async def set_timezone(self, timezone: str) -> TimezoneStatus:
        ensure_timezone_exists(timezone)
        self._timezone = timezone
        return await self.status()
