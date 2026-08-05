"""Scelta delle implementazioni all'avvio (docs 02 — Organizzazione del codice).

È l'unico punto del progetto che sa se stiamo girando in mock o sul ferro: da qui in poi i
router vedono solo dei `Protocol` e non possono comportarsi diversamente nei due casi.
"""

import logging
from dataclasses import dataclass

from src.services.health import HealthService
from src.services.health.mock import MockHealthService
from src.services.health.real import SystemHealthService
from src.services.jobs import JobRegistry
from src.services.network import NetworkService
from src.services.network.mock import MockNetworkService
from src.services.network.real import NmcliNetworkService
from src.services.timezone import TimezoneService
from src.services.timezone.mock import MockTimezoneService
from src.services.timezone.real import TimedatectlTimezoneService
from src.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Services:
    """Le implementazioni attive, costruite una volta sola e iniettate nei router."""

    health: HealthService
    network: NetworkService
    timezone: TimezoneService
    # Il registro dei job non ha un mock: è tutto in memoria, funziona identico ovunque. A
    # essere finte sono semmai le operazioni che ci girano dentro.
    jobs: JobRegistry


def build_services(settings: Settings) -> Services:
    health: HealthService
    network: NetworkService
    timezone: TimezoneService
    if settings.mock:
        health = MockHealthService(settings)
        network = MockNetworkService(settings)
        timezone = MockTimezoneService(settings)
    else:
        health = SystemHealthService(settings)
        network = NmcliNetworkService(settings)
        timezone = TimedatectlTimezoneService(settings)
    logger.info("Implementazioni %s attive", "mock" if settings.mock else "reali")
    return Services(health=health, network=network, timezone=timezone, jobs=JobRegistry())
