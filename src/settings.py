"""Configurazione del servizio, letta dalle variabili d'ambiente.

I default sono pensati per non dover configurare niente: in produzione puntano ai percorsi
reali della macchina (`/etc/g2`, `/home/pi/printer_data`), in sviluppo a una cartella dentro il
repository, così lo stesso codice gira su macOS senza toccare `/etc`.
"""

import os
import platform
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# Prefisso di *tutti* gli endpoint, Swagger compreso. Non è configurabile: è una convenzione
# fissata insieme alla regola nginx `location ^~ /service/` (docs 02 e 05), e cambiarla da una
# variabile d'ambiente vorrebbe dire poter rompere il routing senza accorgersene.
API_PREFIX = "/service"

# Radice del repository: `src/settings.py` → `src/` → repo.
REPO_ROOT = Path(__file__).resolve().parent.parent

# Sostituto locale di `/etc/g2` e `~/printer_data` quando si sviluppa fuori dalla macchina.
DEV_DATA_DIR = REPO_ROOT / ".devdata"

# In produzione il servizio gira come root, ma `printer_data` appartiene all'utente `pi` (è
# Moonraker a possederla): `Path.home()` darebbe `/root` ed è la strada più rapida per scrivere
# nel posto sbagliato. Il percorso è quindi esplicito, non derivato dall'utente corrente.
PRINTER_DATA_DIR = Path("/home/pi/printer_data")
ETC_DIR = Path("/etc/g2")

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class Settings:
    """Configurazione immutabile, decisa una volta sola all'avvio."""

    host: str
    port: int
    mock: bool
    etc_dir: Path
    printer_data_dir: Path

    @property
    def serial_file(self) -> Path:
        """Seriale di fabbrica (vedi docs 04). Può non esistere: è la condizione normale di
        una macchina non ancora configurata."""
        return self.etc_dir / "serial"

    @property
    def printer_config_dir(self) -> Path:
        """Cartella delle configurazioni Klipper/Kalico, quella che legge Moonraker."""
        return self.printer_data_dir / "config"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        environ = os.environ if env is None else env
        mock = _as_bool(environ.get("G2_SERVICE_MOCK"), default=not _is_linux())
        return cls(
            host=environ.get("G2_SERVICE_HOST", "0.0.0.0"),
            port=_as_int(environ.get("G2_SERVICE_PORT"), default=8000),
            mock=mock,
            etc_dir=_as_path(
                environ.get("G2_SERVICE_ETC_DIR"),
                default=DEV_DATA_DIR / "etc" / "g2" if mock else ETC_DIR,
            ),
            printer_data_dir=_as_path(
                environ.get("G2_SERVICE_PRINTER_DATA_DIR"),
                default=DEV_DATA_DIR / "printer_data" if mock else PRINTER_DATA_DIR,
            ),
        )


def _is_linux() -> bool:
    """Fuori da Linux `nmcli` e `timedatectl` non esistono: il mock si attiva da solo, senza
    dover ricordarsi di esportare una variabile a ogni sessione di sviluppo (docs 05)."""
    return platform.system() == "Linux"


def _as_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"Valore booleano non riconosciuto: {raw!r}")


def _as_int(raw: str | None, *, default: int) -> int:
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _as_path(raw: str | None, *, default: Path) -> Path:
    if raw is None or not raw.strip():
        return default
    return Path(raw).expanduser()
