"""Implementazione reale di `NetworkService`, sopra `nmcli`."""

import logging
from typing import Any

from src.errors import InternalError, JobFailure, NotFoundError, SystemToolUnavailableError
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
from src.services.network.nmcli import (
    CONNECT_TIMEOUT,
    CONNECT_WAIT,
    ETHERNET_DEVICE,
    SCAN_TIMEOUT,
    WIFI_DEVICE,
    NmcliAccessPoint,
    NmcliDevice,
    NmcliExit,
    NmcliProfile,
    ip_from_detail,
    nmcli,
    parse_access_points,
    parse_bool,
    parse_detail,
    parse_devices,
    parse_state,
    parse_timestamp,
    split_terse,
)
from src.services.system import DEFAULT_TIMEOUT, CommandResult
from src.settings import Settings

logger = logging.getLogger(__name__)

# I tipi che NetworkManager usa per una connessione WiFi: il primo nelle versioni recenti, il
# secondo in quelle più vecchie.
_WIFI_PROFILE_TYPES = {"wifi", "802-11-wireless"}

_TYPE_BY_NMCLI = {"ethernet": InterfaceType.ETHERNET, "wifi": InterfaceType.WIFI}

# Quale interfaccia mostrare come `adapter`. Prima chi è più vicino a essere connesso, e a
# parità di stato l'Ethernet: è quella che il sistema usa di default ed è la risposta più utile
# da mostrare all'utente (docs 03).
_STATE_PRIORITY = {
    InterfaceState.CONNECTED: 0,
    InterfaceState.CONNECTING: 1,
    InterfaceState.DISCONNECTED: 2,
    InterfaceState.UNAVAILABLE: 3,
    InterfaceState.UNMANAGED: 4,
    InterfaceState.UNKNOWN: 5,
}
_TYPE_PRIORITY = {InterfaceType.ETHERNET: 0, InterfaceType.WIFI: 1}

# Marcatori nei messaggi di `nmcli` (in inglese: i comandi girano con LC_ALL=C).
_AUTH_MARKERS = ("secrets were required", "no secrets", "802-1x", "psk", "invalid password")
_NOT_FOUND_MARKERS = ("no network with ssid", "not found")


class NmcliNetworkService:
    """Parla con NetworkManager. Gira solo su Linux, e solo dove `nmcli` esiste."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ------------------------------------------------------------------ stato unificato

    async def status(self) -> NetworkStatus:
        devices = [device for device in await self._devices() if device.type in _TYPE_BY_NMCLI]
        interfaces = [
            NetworkInterface(
                device=device.device, type=_TYPE_BY_NMCLI[device.type], state=device.state
            )
            for device in devices
        ]
        adapter = _pick_adapter(devices)
        detail = await self._detail(adapter.device)
        signal_info = None
        if adapter.type is InterfaceType.WIFI and adapter.state is InterfaceState.CONNECTED:
            signal_info = await self._current_signal()
        return NetworkStatus(
            adapter=adapter,
            # Senza connessione i campi ci sono e valgono `null`: il client ha una forma sola.
            ip=ip_from_detail(detail) if adapter.state is InterfaceState.CONNECTED else IpInfo(),
            signal_info=signal_info,
            interfaces=interfaces,
        )

    async def _current_signal(self) -> SignalInfo | None:
        """Segnale della rete a cui siamo associati, dalla cache di scansione di NM."""
        current = next((ap for ap in await self._access_points() if ap.in_use), None)
        if current is None:
            logger.warning("Connessi in WiFi ma nessun access point risulta in uso")
            return None
        return SignalInfo(signal_strength=current.signal, ssid=current.ssid)

    # ------------------------------------------------------------------------ scansione

    async def wifi_networks(self, *, rescan: bool = False) -> list[WifiNetwork]:
        access_points = await self._access_points(rescan=rescan)
        # Lo stesso SSID compare una volta per access point (due bande, più ripetitori): per
        # un elenco da mostrare all'utente si tiene il segnale migliore.
        strongest: dict[str, NmcliAccessPoint] = {}
        for access_point in access_points:
            known = strongest.get(access_point.ssid)
            if known is None or access_point.signal > known.signal:
                strongest[access_point.ssid] = access_point
        networks = [
            WifiNetwork(
                ssid=access_point.ssid,
                signal_strength=min(access_point.signal, 100),
                security=access_point.security,
                frequency=access_point.frequency,
                is_hidden=access_point.is_hidden,
            )
            for access_point in strongest.values()
        ]
        networks.sort(key=lambda network: (-network.signal_strength, network.ssid))
        return networks

    async def _access_points(self, *, rescan: bool = False) -> list[NmcliAccessPoint]:
        result = await self._wifi_list(rescan=rescan)
        if not result.ok and rescan:
            # NetworkManager rifiuta una scansione richiesta troppo presto dopo la
            # precedente. Restituire l'elenco in cache è molto meglio di un 503: è comunque
            # aggiornato di pochi secondi.
            logger.warning("Scansione forzata rifiutata, uso la cache: %s", result.stderr.strip())
            result = await self._wifi_list(rescan=False)
        if not result.ok:
            raise SystemToolUnavailableError(
                f"Scansione WiFi non riuscita: {result.stderr.strip() or 'errore sconosciuto'}"
            )
        return parse_access_points(result.stdout)

    async def _wifi_list(self, *, rescan: bool) -> CommandResult:
        return await nmcli(
            "--terse",
            "--fields",
            "IN-USE,SIGNAL,SECURITY,FREQ,SSID",
            "device",
            "wifi",
            "list",
            "ifname",
            WIFI_DEVICE,
            "--rescan",
            "yes" if rescan else "no",
            timeout=SCAN_TIMEOUT if rescan else DEFAULT_TIMEOUT,
        )

    # ------------------------------------------------------------------------ connetti

    async def wifi_connect(self, ssid: str, password: str | None) -> dict[str, Any]:
        """Corpo del job `wifi.connect`.

        Attenzione a leggere il seguito sapendo che **l'IP della macchina cambia** mentre
        questo gira: la richiesta HTTP che ha avviato il job è già caduta, e l'unico modo che
        il client ha di sapere com'è finita è ricollegarsi al nuovo indirizzo e leggere il job.
        """
        profile = await self._profile_for(ssid)
        if password is not None and profile is not None:
            # `device wifi connect` riuserebbe il profilo salvato *ignorando* la password
            # appena ricevuta: chi sta correggendo una password sbagliata resterebbe bloccato
            # sul vecchio valore senza capire perché.
            await self._delete_profiles([profile])
            profile = None

        result = await self._activate(ssid, password, profile)
        if not result.ok:
            if profile is None:
                # Un tentativo fallito può lasciare in giro il profilo appena creato: una rete
                # a cui non ci si è mai connessi non deve comparire fra quelle salvate.
                await self._delete_profiles(await self._profiles_for(ssid))
            raise _connect_failure(result)

        await self._restore_autoconnect(ssid)
        detail = await self._detail(WIFI_DEVICE)
        return {"ssid": ssid, "ip": ip_from_detail(detail).model_dump(by_alias=True)}

    async def _activate(
        self, ssid: str, password: str | None, profile: NmcliProfile | None
    ) -> CommandResult:
        if profile is not None:
            return await nmcli(
                "--wait",
                str(CONNECT_WAIT),
                "connection",
                "up",
                "uuid",
                profile.uuid,
                timeout=CONNECT_TIMEOUT,
            )
        args = ["--wait", str(CONNECT_WAIT), "device", "wifi", "connect", ssid]
        if password:
            args += ["password", password]
        args += ["ifname", WIFI_DEVICE]
        return await nmcli(*args, timeout=CONNECT_TIMEOUT)

    async def _restore_autoconnect(self, ssid: str) -> None:
        """`disconnect` spegne l'autoconnect: connettersi di nuovo deve riaccenderlo, o al
        riavvio la macchina non tornerebbe sulla rete che l'utente ha appena scelto."""
        profile = await self._profile_for(ssid)
        if profile is None or profile.autoconnect:
            return
        result = await nmcli(
            "connection", "modify", "uuid", profile.uuid, "connection.autoconnect", "yes"
        )
        if not result.ok:
            # Non è un motivo per far fallire un job che ha già connesso la macchina.
            logger.warning("Autoconnect non riattivato su %r: %s", ssid, result.stderr.strip())

    # --------------------------------------------------------------------- disconnetti

    async def wifi_disconnect(self) -> dict[str, Any]:
        detail = await self._detail(WIFI_DEVICE)
        uuid = _value(detail, "GENERAL.CON-UUID")
        if uuid is None:
            return {"ssid": None, "alreadyDisconnected": True}
        ssid = await self._profile_ssid(uuid) or _value(detail, "GENERAL.CONNECTION")

        # L'ordine conta: prima si spegne l'autoconnect, poi si abbassa. Al contrario
        # NetworkManager farebbe in tempo a riconnettersi da solo, e il comando sembrerebbe
        # semplicemente non funzionare.
        autoconnect = await nmcli(
            "connection", "modify", "uuid", uuid, "connection.autoconnect", "no"
        )
        if not autoconnect.ok:
            logger.warning("Autoconnect non spento su %s: %s", uuid, autoconnect.stderr.strip())

        # `device disconnect` e non `connection down`: quest'ultimo lascerebbe NetworkManager
        # libero di agganciare subito un'altra rete salvata, e per l'utente sarebbe come non
        # essersi disconnesso affatto.
        result = await nmcli("device", "disconnect", WIFI_DEVICE, timeout=CONNECT_TIMEOUT)
        if not result.ok:
            raise JobFailure(
                "INTERNAL_ERROR",
                f"Disconnessione non riuscita: {result.stderr.strip() or 'errore sconosciuto'}",
            )
        return {"ssid": ssid, "alreadyDisconnected": False}

    # -------------------------------------------------------------------- reti salvate

    async def saved_networks(self) -> list[SavedNetwork]:
        profiles = await self._profiles()
        networks = [
            SavedNetwork(ssid=p.ssid, autoconnect=p.autoconnect, last_used=p.last_used)
            for p in profiles
        ]
        # Le usate di recente in cima, quelle mai usate in fondo.
        networks.sort(key=_saved_sort_key)
        return networks

    async def forget_network(self, ssid: str) -> None:
        profiles = await self._profiles_for(ssid)
        if not profiles:
            raise NotFoundError(f"Rete non salvata: {ssid}")
        failures = await self._delete_profiles(profiles)
        if failures:
            raise InternalError(f"Rete non rimossa: {failures[0]}")

    async def _delete_profiles(self, profiles: list[NmcliProfile]) -> list[str]:
        failures = []
        for profile in profiles:
            result = await nmcli("connection", "delete", "uuid", profile.uuid)
            if not result.ok:
                failures.append(result.stderr.strip() or f"uuid {profile.uuid}")
        return failures

    # ----------------------------------------------------------------------- ethernet

    async def ethernet_status(self) -> EthernetStatus:
        detail = await self._detail(ETHERNET_DEVICE)
        state = _state_from_detail(detail)
        uuid = _value(detail, "GENERAL.CON-UUID")
        return EthernetStatus(
            device=ETHERNET_DEVICE,
            cable_connected=_cable_connected(detail, state),
            state=state,
            ip=ip_from_detail(detail) if state is InterfaceState.CONNECTED else IpInfo(),
            addressing=await self._addressing(uuid) if uuid else None,
        )

    async def _addressing(self, uuid: str) -> Addressing | None:
        result = await nmcli("--terse", "--fields", "ipv4.method", "connection", "show", "uuid", uuid)
        if not result.ok:
            return None
        method = parse_detail(result.stdout).get("ipv4.method", "").strip().lower()
        if method == "auto":
            return Addressing.DHCP
        if method == "manual":
            return Addressing.STATIC
        # `link-local`, `shared`, `disabled`: nessuna delle due risposte previste sarebbe vera.
        return None

    # ------------------------------------------------------------------------ interni

    async def _devices(self) -> list[NmcliDevice]:
        result = await nmcli(
            "--terse", "--fields", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"
        )
        if not result.ok:
            raise SystemToolUnavailableError(
                f"Elenco interfacce non disponibile: {result.stderr.strip() or 'errore sconosciuto'}"
            )
        return parse_devices(result.stdout)

    async def _detail(self, device: str) -> dict[str, str]:
        """Tutti i campi di `device show`.

        Senza `--fields`: chiedere campi specifici significa che una versione di `nmcli` che
        non ne conosce uno fa fallire l'intero comando, e per un endpoint di stato non vale la
        pena. Un device inesistente restituisce un dizionario vuoto, non un errore: `/status`
        deve rispondere comunque.
        """
        result = await nmcli("--terse", "device", "show", device)
        if not result.ok:
            logger.warning("Dettagli di %s non disponibili: %s", device, result.stderr.strip())
            return {}
        return parse_detail(result.stdout)

    async def _profiles(self) -> list[NmcliProfile]:
        """Le connessioni WiFi salvate, con i dati che stanno solo dentro ogni profilo."""
        result = await nmcli("--terse", "--fields", "UUID,TYPE,NAME", "connection", "show")
        if not result.ok:
            raise SystemToolUnavailableError(
                f"Elenco reti salvate non disponibile: {result.stderr.strip() or 'errore sconosciuto'}"
            )
        profiles = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            fields = split_terse(line, maxsplit=2)
            if len(fields) < 3 or fields[1].strip().lower() not in _WIFI_PROFILE_TYPES:
                continue
            uuid, _, name = fields[0].strip(), fields[1], fields[2]
            profile = await self._profile_detail(uuid, name)
            if profile is not None:
                profiles.append(profile)
        return profiles

    async def _profile_detail(self, uuid: str, name: str) -> NmcliProfile | None:
        result = await nmcli(
            "--terse",
            "--fields",
            "802-11-wireless.ssid,connection.autoconnect,connection.timestamp",
            "connection",
            "show",
            "uuid",
            uuid,
        )
        if not result.ok:
            logger.warning("Profilo %s illeggibile: %s", uuid, result.stderr.strip())
            return None
        detail = parse_detail(result.stdout)
        return NmcliProfile(
            uuid=uuid,
            name=name,
            # Il nome del profilo di solito coincide con l'SSID, ma non è garantito: conta
            # quello dentro le impostazioni.
            ssid=detail.get("802-11-wireless.ssid") or name,
            autoconnect=parse_bool(detail.get("connection.autoconnect")),
            last_used=parse_timestamp(detail.get("connection.timestamp")),
        )

    async def _profile_ssid(self, uuid: str) -> str | None:
        result = await nmcli(
            "--terse", "--fields", "802-11-wireless.ssid", "connection", "show", "uuid", uuid
        )
        if not result.ok:
            return None
        return parse_detail(result.stdout).get("802-11-wireless.ssid") or None

    async def _profiles_for(self, ssid: str) -> list[NmcliProfile]:
        return [profile for profile in await self._profiles() if profile.ssid == ssid]

    async def _profile_for(self, ssid: str) -> NmcliProfile | None:
        profiles = await self._profiles_for(ssid)
        return profiles[0] if profiles else None


# --------------------------------------------------------------------------- funzioni pure


def _value(detail: dict[str, str], key: str) -> str | None:
    value = detail.get(key, "").strip()
    return None if value in {"", "--"} else value


def _saved_sort_key(network: SavedNetwork) -> tuple[bool, float]:
    if network.last_used is None:
        return (True, 0.0)
    return (False, -network.last_used.timestamp())


def _pick_adapter(devices: list[NmcliDevice]) -> Adapter:
    """Sceglie l'interfaccia da presentare come connessione attiva."""
    if not devices:
        # Nessuna interfaccia nota: l'adapter c'è comunque, con lo stato esplicito. Il client
        # non deve mai trovarsi davanti un oggetto assente (docs 03).
        logger.warning("NetworkManager non riporta né Ethernet né WiFi")
        return Adapter(
            device=WIFI_DEVICE, type=InterfaceType.WIFI, state=InterfaceState.UNAVAILABLE
        )
    best = min(
        devices,
        key=lambda d: (_STATE_PRIORITY[d.state], _TYPE_PRIORITY[_TYPE_BY_NMCLI[d.type]]),
    )
    return Adapter(
        device=best.device,
        type=_TYPE_BY_NMCLI[best.type],
        state=best.state,
        # Il nome della connessione ha senso solo se ce n'è una attiva.
        connection=best.connection if best.state is InterfaceState.CONNECTED else None,
    )


def _state_from_detail(detail: dict[str, str]) -> InterfaceState:
    raw = detail.get("GENERAL.STATE")
    return parse_state(raw) if raw else InterfaceState.UNAVAILABLE


def _cable_connected(detail: dict[str, str], state: InterfaceState) -> bool:
    carrier = _value(detail, "WIRED-PROPERTIES.CARRIER")
    if carrier is not None:
        return carrier.lower() == "on"
    # Senza il campo del carrier resta l'indizio dello stato: NetworkManager marca
    # `unavailable` un'interfaccia cablata senza link.
    return state not in {
        InterfaceState.UNAVAILABLE,
        InterfaceState.UNMANAGED,
        InterfaceState.UNKNOWN,
    }


def _connect_failure(result: CommandResult) -> JobFailure:
    """Traduce un tentativo di connessione fallito in uno degli esiti previsti (docs 03).

    Una password sbagliata **non** è un errore HTTP: l'operazione è stata accettata ed
    eseguita, ha solo dato esito negativo.
    """
    text = f"{result.stderr}\n{result.stdout}".lower()
    if result.returncode == NmcliExit.TIMEOUT:
        return JobFailure("WIFI_TIMEOUT", "Associazione non completata entro il limite")
    if result.returncode == NmcliExit.NOT_FOUND or any(m in text for m in _NOT_FOUND_MARKERS):
        return JobFailure("WIFI_NETWORK_NOT_FOUND", "Rete non trovata in scansione")
    if any(marker in text for marker in _AUTH_MARKERS):
        return JobFailure("WIFI_AUTH_FAILED", "Password errata o autenticazione rifiutata")
    if "timeout" in text:
        return JobFailure("WIFI_TIMEOUT", "Associazione non completata entro il limite")
    # Un fallimento che non sappiamo classificare non va travestito da uno degli esiti
    # previsti: il messaggio di nmcli è l'unica cosa utile che possiamo passare.
    return JobFailure(
        "INTERNAL_ERROR",
        f"Connessione non riuscita: {result.stderr.strip() or 'errore sconosciuto'}",
    )
