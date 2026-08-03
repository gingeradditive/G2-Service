"""Implementazione mock di `NetworkService`.

Non è un "restituisci qualcosa": tiene uno **stato** e le operazioni lo modificano, così il
giro completo — scansione, connessione, stato che cambia, disconnessione — si sviluppa su
macOS come sulla macchina vera. I job hanno anche una durata finta di qualche secondo,
altrimenti finirebbero prima che il client faccia in tempo a vederli `running`.

Gli scenari di fallimento selezionabili (`G2_SERVICE_MOCK_SCENARIO`) sono `DEV-2`: qui una
connessione con la password sbagliata riesce comunque.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.errors import JobFailure, NotFoundError
from src.models.network import (
    Adapter,
    Addressing,
    EthernetStatus,
    InterfaceState,
    InterfaceType,
    IpInfo,
    NetworkInterface,
    NetworkStatus,
    SavedNetwork,
    SignalInfo,
    WifiNetwork,
)
from src.services.network.nmcli import ETHERNET_DEVICE, WIFI_DEVICE
from src.settings import Settings

# Quanto durano le finte operazioni lunghe.
_CONNECT_DELAY = 2.0
_DISCONNECT_DELAY = 1.0
_RESCAN_DELAY = 1.5

_MOCK_IP = IpInfo(
    ipv4="192.168.1.42",
    ipv6="2a01:e11:1004:1a40:ba27:ebff:fe1a:2b3c",
    mac="b8:27:eb:1a:2b:3c",
)


@dataclass
class _AccessPoint:
    ssid: str
    signal: int
    security: str
    frequency: int
    hidden: bool = False


@dataclass
class _Saved:
    ssid: str
    autoconnect: bool
    last_used: datetime | None


def _default_access_points() -> list[_AccessPoint]:
    """Segnali diversi, reti protette e aperte, due bande e una rete nascosta: gli stessi casi
    che l'interfaccia deve saper disegnare."""
    return [
        _AccessPoint("Ginger-Lab", 88, "WPA2", 5180),
        _AccessPoint("Ginger-Ospiti", 71, "open", 2437),
        _AccessPoint("Officina", 54, "WPA1 WPA2", 2412),
        _AccessPoint("TIM-38271640", 37, "WPA2", 2462),
        _AccessPoint("Vodafone-Casa", 22, "WPA3", 5745),
        _AccessPoint("", 45, "WPA2", 2422, hidden=True),
    ]


class MockNetworkService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._access_points = _default_access_points()
        self._saved = [
            _Saved("Ginger-Lab", True, datetime.now(timezone.utc) - timedelta(minutes=12)),
            _Saved("Officina", True, datetime.now(timezone.utc) - timedelta(days=9)),
            _Saved("TIM-38271640", False, None),
        ]
        self._connected_ssid: str | None = "Ginger-Lab"
        # Cavo staccato: è lo stato più utile in sviluppo, quello in cui il WiFi conta.
        self._cable_connected = False

    # ------------------------------------------------------------------------- letture

    async def status(self) -> NetworkStatus:
        interfaces = [
            NetworkInterface(
                device=ETHERNET_DEVICE,
                type=InterfaceType.ETHERNET,
                state=(
                    InterfaceState.CONNECTED
                    if self._cable_connected
                    else InterfaceState.UNAVAILABLE
                ),
            ),
            NetworkInterface(
                device=WIFI_DEVICE,
                type=InterfaceType.WIFI,
                state=(
                    InterfaceState.CONNECTED
                    if self._connected_ssid
                    else InterfaceState.DISCONNECTED
                ),
            ),
        ]
        if self._cable_connected:
            return NetworkStatus(
                adapter=Adapter(
                    device=ETHERNET_DEVICE,
                    type=InterfaceType.ETHERNET,
                    state=InterfaceState.CONNECTED,
                    connection="Wired connection 1",
                ),
                ip=_MOCK_IP,
                signal_info=None,
                interfaces=interfaces,
            )
        if self._connected_ssid:
            access_point = self._find(self._connected_ssid)
            return NetworkStatus(
                adapter=Adapter(
                    device=WIFI_DEVICE,
                    type=InterfaceType.WIFI,
                    state=InterfaceState.CONNECTED,
                    connection=self._connected_ssid,
                ),
                ip=_MOCK_IP,
                signal_info=SignalInfo(
                    signal_strength=access_point.signal if access_point else 60,
                    ssid=self._connected_ssid,
                ),
                interfaces=interfaces,
            )
        return NetworkStatus(
            adapter=Adapter(
                device=WIFI_DEVICE, type=InterfaceType.WIFI, state=InterfaceState.DISCONNECTED
            ),
            ip=IpInfo(),
            signal_info=None,
            interfaces=interfaces,
        )

    async def wifi_networks(self, *, rescan: bool = False) -> list[WifiNetwork]:
        if rescan:
            await asyncio.sleep(_RESCAN_DELAY)
        networks = [
            WifiNetwork(
                ssid=access_point.ssid,
                signal_strength=access_point.signal,
                security=access_point.security,
                frequency=access_point.frequency,
                is_hidden=access_point.hidden,
            )
            for access_point in self._access_points
        ]
        networks.sort(key=lambda network: (-network.signal_strength, network.ssid))
        return networks

    async def saved_networks(self) -> list[SavedNetwork]:
        return [
            SavedNetwork(ssid=s.ssid, autoconnect=s.autoconnect, last_used=s.last_used)
            for s in self._saved
        ]

    async def ethernet_status(self) -> EthernetStatus:
        connected = self._cable_connected
        return EthernetStatus(
            device=ETHERNET_DEVICE,
            cable_connected=connected,
            state=InterfaceState.CONNECTED if connected else InterfaceState.UNAVAILABLE,
            ip=_MOCK_IP if connected else IpInfo(),
            addressing=Addressing.DHCP if connected else None,
        )

    # ---------------------------------------------------------------------- scritture

    async def wifi_connect(self, ssid: str, password: str | None) -> dict[str, Any]:
        await asyncio.sleep(_CONNECT_DELAY)
        if self._find(ssid) is None:
            raise JobFailure("WIFI_NETWORK_NOT_FOUND", f"Rete non trovata in scansione: {ssid}")
        self._connected_ssid = ssid
        saved = self._find_saved(ssid)
        if saved is None:
            self._saved.append(_Saved(ssid, True, datetime.now(timezone.utc)))
        else:
            saved.autoconnect = True
            saved.last_used = datetime.now(timezone.utc)
        return {"ssid": ssid, "ip": _MOCK_IP.model_dump(by_alias=True)}

    async def wifi_disconnect(self) -> dict[str, Any]:
        await asyncio.sleep(_DISCONNECT_DELAY)
        if self._connected_ssid is None:
            return {"ssid": None, "alreadyDisconnected": True}
        ssid = self._connected_ssid
        saved = self._find_saved(ssid)
        if saved is not None:
            saved.autoconnect = False
        self._connected_ssid = None
        return {"ssid": ssid, "alreadyDisconnected": False}

    async def forget_network(self, ssid: str) -> None:
        saved = self._find_saved(ssid)
        if saved is None:
            raise NotFoundError(f"Rete non salvata: {ssid}")
        self._saved.remove(saved)
        if self._connected_ssid == ssid:
            self._connected_ssid = None

    # ------------------------------------------------------------------------ interni

    def _find(self, ssid: str) -> _AccessPoint | None:
        return next((ap for ap in self._access_points if ap.ssid == ssid), None)

    def _find_saved(self, ssid: str) -> _Saved | None:
        return next((s for s in self._saved if s.ssid == ssid), None)
