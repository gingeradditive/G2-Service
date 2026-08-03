"""Implementazione reale di `HealthService`."""

import asyncio
from collections.abc import Sequence

from src.errors import SystemToolUnavailableError
from src.models.health import HealthChecks
from src.services.health import serial_configured
from src.services.system import run_command
from src.settings import Settings

# I check devono restare rapidi: `/service/health` è l'endpoint che GingerView interroga per
# capire se il servizio c'è, e non può metterci dieci secondi per dire di sì.
PROBE_TIMEOUT = 3.0


class SystemHealthService:
    """Interroga davvero i comandi di sistema."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def checks(self) -> HealthChecks:
        network_manager, timedatectl = await asyncio.gather(
            # Non basta che l'eseguibile esista: `nmcli general status` fallisce anche quando
            # `nmcli` c'è ma NetworkManager è giù, che è il caso che vogliamo distinguere.
            self._responds(["nmcli", "--terse", "general", "status"]),
            self._responds(["timedatectl", "show"]),
        )
        return HealthChecks(
            network_manager=network_manager,
            timedatectl=timedatectl,
            serial_configured=serial_configured(self._settings),
        )

    async def _responds(self, argv: Sequence[str]) -> bool:
        try:
            result = await run_command(argv, timeout=PROBE_TIMEOUT)
        except SystemToolUnavailableError:
            return False
        return result.ok
