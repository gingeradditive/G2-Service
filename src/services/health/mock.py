"""Implementazione mock di `HealthService`."""

from src.mock_scenarios import MockScenario
from src.models.health import HealthChecks
from src.services.health import serial_configured
from src.settings import Settings


class MockHealthService:
    """Finge una macchina sana.

    Fuori da Linux `nmcli` e `timedatectl` non esistono: i check reali sarebbero sempre
    `false` e l'endpoint non direbbe niente di utile in sviluppo. `serialConfigured` invece
    resta vero: è un file locale, e nei percorsi di sviluppo si può creare davvero.

    Lo scenario `nm-unavailable` (`G2_SERVICE_MOCK_SCENARIO`) riporta `networkManager` a
    `false`, coerente con `MockNetworkService` che nello stesso scenario fa fallire ogni
    operazione di rete.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def checks(self) -> HealthChecks:
        return HealthChecks(
            network_manager=self._settings.mock_scenario is not MockScenario.NM_UNAVAILABLE,
            timedatectl=True,
            serial_configured=serial_configured(self._settings),
        )
