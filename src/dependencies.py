"""Dipendenze dei router.

Un router non costruisce mai un servizio: se lo chiede con `Depends` e riceve quello scelto
all'avvio. È anche il gancio con cui un test può sostituirne uno singolo
(`app.dependency_overrides[get_health_service] = ...`) senza toccare il resto.
"""

from typing import Annotated

from fastapi import Depends, Request

from src.services.container import Services
from src.services.health import HealthService
from src.services.jobs import JobRegistry
from src.services.network import NetworkService
from src.services.timezone import TimezoneService
from src.services.usb import UsbService
from src.settings import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_health_service(services: Annotated[Services, Depends(get_services)]) -> HealthService:
    return services.health


def get_network_service(services: Annotated[Services, Depends(get_services)]) -> NetworkService:
    return services.network


def get_timezone_service(
    services: Annotated[Services, Depends(get_services)],
) -> TimezoneService:
    return services.timezone


def get_usb_service(services: Annotated[Services, Depends(get_services)]) -> UsbService:
    return services.usb


def get_job_registry(services: Annotated[Services, Depends(get_services)]) -> JobRegistry:
    return services.jobs
