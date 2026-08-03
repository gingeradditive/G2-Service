"""Schemi di `GET /service/health` (docs 03 — Health)."""

from typing import Literal

from src.models.base import CamelModel


class HealthChecks(CamelModel):
    """Disponibilità delle funzionalità che dipendono dalla macchina sottostante."""

    network_manager: bool
    timedatectl: bool
    serial_configured: bool


class HealthResponse(CamelModel):
    # `status` resta "ok" anche con dei check a `false`: il servizio è vivo, semplicemente su
    # questa macchina una funzionalità non è disponibile. Serve a GingerView per sapere che
    # G2-Service c'è e che versione parla.
    status: Literal["ok"] = "ok"
    version: str
    checks: HealthChecks
