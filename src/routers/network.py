"""Endpoint di rete (docs 03 — Stato di rete, WiFi, Ethernet)."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, status

from src.dependencies import get_job_registry, get_network_service
from src.errors import (
    ConflictError,
    NotFoundError,
    SystemToolUnavailableError,
    error_responses,
)
from src.models.jobs import JobResponse
from src.models.network import (
    EthernetStatus,
    NetworkStatus,
    SavedNetwork,
    WifiConnectRequest,
    WifiNetwork,
)
from src.services.jobs import JobRecord, JobRegistry
from src.services.network import WIFI_CONNECT_JOB, WIFI_DISCONNECT_JOB, NetworkService

router = APIRouter(prefix="/network", tags=["network"])

NetworkDep = Annotated[NetworkService, Depends(get_network_service)]
JobsDep = Annotated[JobRegistry, Depends(get_job_registry)]

_UNAVAILABLE = error_responses(SystemToolUnavailableError)


@router.get(
    "/status",
    summary="Stato di rete unificato",
    description=(
        "Descrive la connessione attiva. Se sono attive sia Ethernet sia WiFi vince "
        "l'Ethernet; se non c'è nessuna connessione `adapter.state` vale `disconnected` e i "
        "campi di `ip` sono `null`. `signalInfo` è presente solo su WiFi."
    ),
    responses=_UNAVAILABLE,
)
async def get_network_status(network: NetworkDep) -> NetworkStatus:
    return await network.status()


@router.get(
    "/wifi/networks",
    summary="Reti WiFi visibili",
    description="Ultima scansione nota di NetworkManager, senza forzarne una nuova.",
    responses=_UNAVAILABLE,
)
async def list_wifi_networks(network: NetworkDep) -> list[WifiNetwork]:
    return await network.wifi_networks()


@router.post(
    "/wifi/rescan",
    summary="Forza una scansione WiFi",
    description="Aspetta i risultati nuovi e restituisce l'elenco aggiornato.",
    responses=_UNAVAILABLE,
)
async def rescan_wifi_networks(network: NetworkDep) -> list[WifiNetwork]:
    return await network.wifi_networks(rescan=True)


@router.post(
    "/wifi/connect",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobResponse,
    summary="Connette a una rete WiFi",
    description=(
        "Operazione asincrona: restituisce un job da seguire su `/service/jobs/{jobId}`.\n\n"
        "**L'indirizzo IP della macchina cambia durante l'operazione**, quindi questa "
        "connessione HTTP cadrà: l'esito va letto ricollegandosi al nuovo indirizzo. Gli "
        "esiti negativi (`WIFI_AUTH_FAILED`, `WIFI_NETWORK_NOT_FOUND`, `WIFI_TIMEOUT`) "
        "arrivano come `status: failed` del job, non come errore HTTP."
    ),
    responses=error_responses(ConflictError, SystemToolUnavailableError),
)
async def connect_wifi(
    network: NetworkDep,
    jobs: JobsDep,
    request: Annotated[WifiConnectRequest, Body()],
) -> JobRecord:
    return jobs.start(
        WIFI_CONNECT_JOB, lambda: network.wifi_connect(request.ssid, request.password)
    )


@router.post(
    "/wifi/disconnect",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobResponse,
    summary="Disconnette dalla rete WiFi",
    description=(
        "Operazione asincrona. Spegne anche l'autoconnect della connessione: senza, "
        "NetworkManager si riconnetterebbe da solo dopo pochi secondi. La rete resta "
        "salvata — per rimuoverla c'è `DELETE /service/network/wifi/saved/{ssid}`."
    ),
    responses=error_responses(ConflictError, SystemToolUnavailableError),
)
async def disconnect_wifi(network: NetworkDep, jobs: JobsDep) -> JobRecord:
    return jobs.start(WIFI_DISCONNECT_JOB, network.wifi_disconnect)


@router.get(
    "/wifi/saved",
    summary="Reti WiFi salvate",
    responses=_UNAVAILABLE,
)
async def list_saved_networks(network: NetworkDep) -> list[SavedNetwork]:
    return await network.saved_networks()


@router.delete(
    "/wifi/saved/{ssid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dimentica una rete salvata",
    responses=error_responses(NotFoundError, SystemToolUnavailableError),
)
async def forget_saved_network(
    network: NetworkDep,
    ssid: Annotated[str, Path(description="SSID della rete da dimenticare")],
) -> None:
    await network.forget_network(ssid)


@router.get(
    "/ethernet/status",
    summary="Stato dell'interfaccia Ethernet",
    description=(
        "`cableConnected` riflette il link fisico e distingue «cavo staccato» da «cavo "
        "attaccato ma senza IP», cosa che lo stato unificato non dà. `addressing` è `null` "
        "quando non c'è una connessione attiva da cui leggerlo."
    ),
    responses=_UNAVAILABLE,
)
async def get_ethernet_status(network: NetworkDep) -> EthernetStatus:
    return await network.ethernet_status()
