"""Servizio di rete: WiFi ed Ethernet (docs 03).

`wifi_connect` e `wifi_disconnect` sono i corpi dei job asincroni: restituiscono il `result`
del job e segnalano un esito negativo previsto con `JobFailure`, non con un errore HTTP.
"""

from typing import Any, Protocol

from src.models.network import EthernetStatus, NetworkStatus, SavedNetwork, WifiNetwork

# Tipi dei job, quelli che compaiono in `GET /service/jobs/{jobId}`. Sono anche la chiave con
# cui il registro impedisce due operazioni sovrapposte dello stesso genere.
WIFI_CONNECT_JOB = "wifi.connect"
WIFI_DISCONNECT_JOB = "wifi.disconnect"


class NetworkService(Protocol):
    async def status(self) -> NetworkStatus:
        """Stato unificato: la connessione attiva, con priorità all'Ethernet."""
        ...

    async def wifi_networks(self, *, rescan: bool = False) -> list[WifiNetwork]:
        """Reti visibili. Con `rescan` forza una scansione e aspetta i risultati nuovi."""
        ...

    async def wifi_connect(self, ssid: str, password: str | None) -> dict[str, Any]:
        """Corpo del job `wifi.connect`."""
        ...

    async def wifi_disconnect(self) -> dict[str, Any]:
        """Corpo del job `wifi.disconnect`."""
        ...

    async def saved_networks(self) -> list[SavedNetwork]:
        ...

    async def forget_network(self, ssid: str) -> None:
        """Solleva `NotFoundError` se la rete non è salvata."""
        ...

    async def ethernet_status(self) -> EthernetStatus:
        ...
