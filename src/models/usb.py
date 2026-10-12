"""Schemi della chiavetta USB (docs 07)."""

from datetime import datetime
from enum import Enum

from pydantic import Field

from src.models.base import CamelModel

# I percorsi arrivano come stringhe relative (alla chiavetta o a `gcodes`): il limite di
# lunghezza è solo una difesa, la validazione vera è nel servizio, dopo averli risolti.
PATH_MAX_LENGTH = 1024


class UsbStatus(CamelModel):
    mounted: bool


class UsbDir(CamelModel):
    name: str


class UsbFile(CamelModel):
    name: str
    size: int
    modified: datetime


class UsbDirectory(CamelModel):
    #: Il percorso normalizzato della cartella elencata, `""` alla radice della chiavetta.
    path: str
    dirs: list[UsbDir]
    files: list[UsbFile]


class OnConflict(str, Enum):
    FAIL = "fail"
    OVERWRITE = "overwrite"
    RENAME = "rename"


class UsbImportRequest(CamelModel):
    source: str = Field(min_length=1, max_length=PATH_MAX_LENGTH)
    dest_dir: str = Field(default="", max_length=PATH_MAX_LENGTH)
    on_conflict: OnConflict = OnConflict.FAIL
