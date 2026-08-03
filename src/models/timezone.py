"""Schemi del fuso orario (docs 03 — Timezone)."""

from pydantic import Field

from src.models.base import CamelModel

# Un identificativo IANA: `Europe/Rome`, `UTC`, `America/Argentina/Buenos_Aires`,
# `Etc/GMT+5`, `America/Port-au-Prince`. Il punto **non** è fra i caratteri ammessi, e questo
# esclude alla radice i `..` — la stringa finisce dentro un percorso sotto `/usr/share/zoneinfo`.
TIMEZONE_PATTERN = r"^[A-Za-z0-9+_-]+(?:/[A-Za-z0-9+_-]+)*$"


class TimezoneStatus(CamelModel):
    timezone: str
    # In sola lettura: su Raspberry Pi OS la sincronizzazione è attiva di default e il Pi non
    # ha un RTC, quindi appena c'è rete l'ora si corregge da sola.
    ntp_synchronized: bool


class TimezoneRequest(CamelModel):
    timezone: str = Field(pattern=TIMEZONE_PATTERN, min_length=1, max_length=64)
