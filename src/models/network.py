"""Schemi di rete (docs 03 — Stato di rete, WiFi, Ethernet)."""

from datetime import datetime
from enum import Enum

from pydantic import Field

from src.models.base import CamelModel


class InterfaceType(str, Enum):
    ETHERNET = "ethernet"
    WIFI = "wifi"


class InterfaceState(str, Enum):
    """Stato di un'interfaccia, normalizzato da quello di NetworkManager.

    `disconnected` e `unavailable` sono due cose diverse ed è la distinzione che serve a
    GingerView: su Ethernet `unavailable` vuol dire cavo staccato, `disconnected` vuol dire
    cavo attaccato ma nessuna connessione attiva.
    """

    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    UNAVAILABLE = "unavailable"
    UNMANAGED = "unmanaged"
    UNKNOWN = "unknown"


class Addressing(str, Enum):
    DHCP = "dhcp"
    STATIC = "static"


class NetworkInterface(CamelModel):
    device: str
    type: InterfaceType
    state: InterfaceState


class Adapter(NetworkInterface):
    """L'interfaccia che descrive la connessione attiva."""

    connection: str | None = None


class IpInfo(CamelModel):
    # Tutti e tre a `null` quando non c'è connessione: i campi restano, cambia il valore.
    ipv4: str | None = None
    # Solo indirizzi globali: un link-local `fe80::` non è utile a nessun client.
    ipv6: str | None = None
    mac: str | None = None


class SignalInfo(CamelModel):
    signal_strength: int = Field(ge=0, le=100, description="Qualità del segnale, 0-100")
    ssid: str


class NetworkStatus(CamelModel):
    adapter: Adapter
    ip: IpInfo
    # Presente solo quando `adapter.type` è `wifi`, altrimenti `null`.
    signal_info: SignalInfo | None = None
    interfaces: list[NetworkInterface]


class WifiNetwork(CamelModel):
    ssid: str
    signal_strength: int = Field(ge=0, le=100)
    # `"open"` per le reti senza cifratura, altrimenti la stringa di NetworkManager
    # (`"WPA2"`, `"WPA1 WPA2"`, `"WPA2 802.1X"`, ...).
    security: str
    frequency: int | None = Field(default=None, description="MHz del canale, es. 2412 o 5180")
    is_hidden: bool = False


class SavedNetwork(CamelModel):
    ssid: str
    autoconnect: bool
    last_used: datetime | None = None


class WifiConnectRequest(CamelModel):
    # Uno SSID è lungo al massimo 32 byte, quindi mai più di 32 caratteri.
    ssid: str = Field(min_length=1, max_length=32)
    # Assente per le reti aperte. Quando c'è, sostituisce quella eventualmente salvata.
    password: str | None = Field(default=None, min_length=1, max_length=64)


class EthernetStatus(CamelModel):
    device: str
    # Stato del link fisico, che lo stato unificato non dà: distingue "cavo staccato" da
    # "cavo attaccato ma senza IP".
    cable_connected: bool
    state: InterfaceState
    ip: IpInfo
    # `null` quando non c'è una connessione attiva da cui leggerlo.
    addressing: Addressing | None = None
