"""Wrapper su `nmcli`: esecuzione, parsing dell'output, codici di uscita.

È la parte più fragile del progetto — il formato di `nmcli` cambia tra versioni — ed è per
questo isolata qui: le funzioni di parsing sono pure e si esercitano con dell'output finto,
senza NetworkManager e senza un Raspberry Pi.

**Due cose vanno sapute prima di toccare questo file.**

*Localizzazione.* `nmcli` traduce sia i messaggi d'errore sia i nomi degli stati: con `LANG`
italiano `device status` stampa `connesso` e ogni confronto qui dentro fallisce. Tutti i
comandi girano quindi con `LC_ALL=C`.

*Escaping.* In modalità `--terse` i campi sono separati da `:`, e i `:` dentro un valore
vengono protetti con `\\` (un MAC diventa `B8\\:27\\:EB\\:...`). Spezzare le righe con uno
`str.split(":")` funziona finché non arriva un SSID con i due punti dentro, e allora sbaglia
in silenzio: si passa sempre da `split_terse()`.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum

from src.errors import SystemToolUnavailableError
from src.models.network import InterfaceState, IpInfo
from src.services.system import DEFAULT_TIMEOUT, CommandResult, run_command

logger = logging.getLogger(__name__)

NMCLI = "nmcli"

# I nomi delle interfacce sono fissi: sono hardware noto e stabile della G2, non serve
# rilevarli a runtime (docs 03). La G2 ha **un solo** adattatore WiFi, quello integrato.
WIFI_DEVICE = "wlan0"
ETHERNET_DEVICE = "eth0"

# Vedi il commento sulla localizzazione in cima al modulo.
_C_LOCALE = {"LC_ALL": "C", "LANG": "C"}

# Una scansione WiFi forzata può prendersi qualche secondo; una connessione molto di più.
SCAN_TIMEOUT = 30.0
CONNECT_WAIT = 45
CONNECT_TIMEOUT = 60.0

# nmcli stampa `--` al posto di un valore assente.
_EMPTY = {"", "--"}


class NmcliExit(IntEnum):
    """Codici di uscita di `nmcli` (vedi `man nmcli`, sezione EXIT STATUS)."""

    SUCCESS = 0
    ERROR = 1
    INVALID_INPUT = 2
    TIMEOUT = 3
    ACTIVATION_FAILED = 4
    DEACTIVATION_FAILED = 5
    DISCONNECT_FAILED = 6
    DELETION_FAILED = 7
    NM_NOT_RUNNING = 8
    NOT_FOUND = 10


@dataclass(frozen=True)
class NmcliDevice:
    device: str
    type: str
    state: InterfaceState
    connection: str | None


@dataclass(frozen=True)
class NmcliAccessPoint:
    ssid: str
    signal: int
    security: str
    frequency: int | None
    in_use: bool

    @property
    def is_hidden(self) -> bool:
        return not self.ssid


@dataclass(frozen=True)
class NmcliProfile:
    """Una connessione salvata."""

    uuid: str
    name: str
    ssid: str
    autoconnect: bool
    last_used: datetime | None


# --------------------------------------------------------------------------- esecuzione


async def nmcli(
    *args: str, timeout: float = DEFAULT_TIMEOUT, check_running: bool = True
) -> CommandResult:
    """Esegue `nmcli` e restituisce l'esito grezzo.

    Un codice di uscita diverso da zero non solleva: quasi sempre è informazione (rete non
    trovata, autenticazione fallita) e va interpretata da chi ha invocato il comando. L'unica
    eccezione è `NM_NOT_RUNNING`, che non è l'esito di un'operazione ma l'assenza del
    sottosistema: diventa `SYSTEM_TOOL_UNAVAILABLE` come se `nmcli` non fosse installato.
    """
    result = await run_command([NMCLI, *args], timeout=timeout, env=_C_LOCALE)
    if check_running and result.returncode == NmcliExit.NM_NOT_RUNNING:
        raise SystemToolUnavailableError("NetworkManager non è in esecuzione")
    return result


# ----------------------------------------------------------------------------- parsing


def split_terse(line: str, maxsplit: int | None = None) -> list[str]:
    """Spezza una riga `--terse` sui `:` non protetti, togliendo l'escaping dai valori.

    `maxsplit` limita il numero di separazioni: tenendo per ultimo il campo che può contenere
    di tutto (SSID, nome della connessione) la riga resta leggibile anche se una versione di
    `nmcli` dimenticasse di proteggerne il contenuto.
    """
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":" and (maxsplit is None or len(fields) < maxsplit):
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def _clean(value: str) -> str | None:
    value = value.strip()
    return None if value in _EMPTY else value


def parse_state(raw: str) -> InterfaceState:
    """Normalizza lo stato di un'interfaccia.

    Va gestita più di una forma: `device status` scrive `connected`, `device show` scrive
    `100 (connected)`, e durante l'associazione compare `connecting (getting IP
    configuration)`. Uno stato che non riconosciamo diventa `unknown` e non un errore: le
    versioni di NetworkManager ne aggiungono, e non è una buona ragione per rompere `/status`.
    """
    text = raw.strip().lower()
    if text[:1].isdigit():
        match = re.search(r"\(([^)]*)", text)
        text = match.group(1) if match else text
    head = text.split("(")[0].strip()
    if head.startswith("connecting"):
        return InterfaceState.CONNECTING
    if head.startswith("connected"):
        return InterfaceState.CONNECTED
    if head in {"disconnected", "deactivating", "failed"}:
        return InterfaceState.DISCONNECTED
    if head == "unavailable":
        return InterfaceState.UNAVAILABLE
    if head == "unmanaged":
        return InterfaceState.UNMANAGED
    return InterfaceState.UNKNOWN


def parse_devices(stdout: str) -> list[NmcliDevice]:
    """Legge `nmcli --terse --fields DEVICE,TYPE,STATE,CONNECTION device status`."""
    devices = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        fields = split_terse(line, maxsplit=3)
        if len(fields) < 4:
            logger.warning("Riga di `device status` non riconosciuta: %r", line)
            continue
        device, device_type, state, connection = fields
        devices.append(
            NmcliDevice(
                device=device.strip(),
                type=device_type.strip().lower(),
                state=parse_state(state),
                connection=_clean(connection),
            )
        )
    return devices


def parse_access_points(stdout: str) -> list[NmcliAccessPoint]:
    """Legge `nmcli --terse --fields IN-USE,SIGNAL,SECURITY,FREQ,SSID device wifi list`.

    Lo SSID è tenuto per ultimo di proposito: è il campo che può contenere qualsiasi cosa.
    """
    access_points = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        fields = split_terse(line, maxsplit=4)
        if len(fields) < 5:
            logger.warning("Riga di `wifi list` non riconosciuta: %r", line)
            continue
        in_use, signal, security, frequency, ssid = fields
        access_points.append(
            NmcliAccessPoint(
                ssid=ssid,
                signal=_parse_int(signal) or 0,
                # Una rete senza cifratura ha il campo vuoto: `"open"` è più esplicito di `""`
                # per un client che deve decidere se chiedere la password.
                security=security.strip() or "open",
                frequency=_parse_int(frequency),
                in_use=in_use.strip() == "*",
            )
        )
    return access_points


def parse_detail(stdout: str) -> dict[str, str]:
    """Legge l'output `CHIAVE:valore` di `nmcli --terse device show <dev>`.

    Le chiavi ripetute sono indicizzate da nmcli (`IP4.ADDRESS[1]`, `IP4.ADDRESS[2]`) e qui
    restano tali: `indexed_values()` le rimette in fila.
    """
    detail = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        fields = split_terse(line, maxsplit=1)
        if len(fields) != 2:
            continue
        detail[fields[0].strip()] = fields[1].strip()
    return detail


def indexed_values(detail: dict[str, str], prefix: str) -> list[str]:
    """Tutti i valori di una chiave indicizzata, in ordine (`IP4.ADDRESS[1]`, `[2]`, ...)."""
    values = []
    for index in range(1, 100):
        value = _clean(detail.get(f"{prefix}[{index}]", ""))
        if value is None:
            break
        values.append(value)
    return values


def ip_from_detail(detail: dict[str, str]) -> IpInfo:
    ipv4 = indexed_values(detail, "IP4.ADDRESS")
    ipv6 = indexed_values(detail, "IP6.ADDRESS")
    return IpInfo(
        ipv4=_strip_prefix_length(ipv4[0]) if ipv4 else None,
        ipv6=_first_global_ipv6(ipv6),
        mac=_clean(detail.get("GENERAL.HWADDR", "")),
    )


def _first_global_ipv6(addresses: list[str]) -> str | None:
    """Scarta i link-local `fe80::`: sono sempre presenti e non servono a nessun client."""
    for address in addresses:
        cleaned = _strip_prefix_length(address)
        if not cleaned.lower().startswith("fe80:"):
            return cleaned
    return None


def _strip_prefix_length(address: str) -> str:
    """`192.168.1.42/24` → `192.168.1.42`."""
    return address.split("/", 1)[0]


def _parse_int(raw: str) -> int | None:
    """Estrae il numero iniziale: `SIGNAL` è già un numero, `FREQ` è `2412 MHz`."""
    match = re.match(r"\s*(\d+)", raw)
    return int(match.group(1)) if match else None


def parse_timestamp(raw: str | None) -> datetime | None:
    """`connection.timestamp` è un epoch Unix; `0` vuol dire "mai usata"."""
    if not raw or not raw.strip().isdigit():
        return None
    seconds = int(raw.strip())
    if seconds <= 0:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def parse_bool(raw: str | None) -> bool:
    return (raw or "").strip().lower() == "yes"
