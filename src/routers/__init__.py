"""Livello HTTP: un modulo per area.

I router non eseguono comandi di sistema — validano l'input, chiamano un servizio e scelgono
il codice di risposta. È la regola che tiene in piedi la struttura (docs 02): finché vale, il
progetto resta sviluppabile su macOS e testabile senza un Raspberry Pi.
"""

from fastapi import APIRouter

from src.routers import health, jobs, network, timezone

#: Tutte le rotte del servizio. `main.py` lo monta sotto il prefisso `/service`, che quindi
#: non va ripetuto nei singoli router.
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(network.router)
api_router.include_router(timezone.router)
api_router.include_router(jobs.router)
