"""Implementazione mock di `HealthService`."""

from src.models.health import HealthChecks
from src.services.health import serial_configured
from src.settings import Settings


class MockHealthService:
    """Finge una macchina sana.

    Fuori da Linux `nmcli` e `timedatectl` non esistono: i check reali sarebbero sempre
    `false` e l'endpoint non direbbe niente di utile in sviluppo. `serialConfigured` invece
    resta vero: è un file locale, e nei percorsi di sviluppo si può creare davvero.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def checks(self) -> HealthChecks:
        return HealthChecks(
            network_manager=True,
            timedatectl=True,
            serial_configured=serial_configured(self._settings),
        )
