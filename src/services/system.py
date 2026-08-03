"""Esecuzione dei comandi di sistema.

È il livello più basso del servizio: `nmcli`, `timedatectl` e chiunque altro passano di qui,
così il timeout e la traduzione dei fallimenti stanno in un punto solo invece di essere
ricopiati in ogni wrapper.

I comandi girano come sottoprocessi *asincroni*: il servizio è a singolo event loop e un
`subprocess.run` bloccante fermerebbe anche le richieste che non c'entrano nulla — per esempio
un `GET /service/health` mentre una connessione WiFi è in corso.
"""

import asyncio
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from src.errors import SystemToolUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


async def run_command(
    argv: Sequence[str],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Esegue un comando e ne restituisce l'esito.

    Un'uscita con codice diverso da zero **non** è un'eccezione: `nmcli` usa il codice di
    uscita per comunicare, e distinguere "password sbagliata" da "NetworkManager non c'è" è
    compito di chi conosce il comando. Sono errori solo i due casi in cui il comando non ha
    potuto parlare affatto — non esiste, o non ha risposto entro il timeout — e diventano
    `SYSTEM_TOOL_UNAVAILABLE`.

    `env` si somma all'ambiente del processo invece di sostituirlo: serve a fissare `LC_ALL`
    per i comandi il cui output viene letto (vedi `services/network/nmcli.py`).
    """
    command = tuple(argv)
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=None if env is None else {**os.environ, **env},
        )
    except OSError as exc:
        raise SystemToolUnavailableError(f"Comando non disponibile: {command[0]}") from exc

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise SystemToolUnavailableError(
            f"{command[0]} non ha risposto entro {timeout:g} secondi"
        ) from exc

    result = CommandResult(
        argv=command,
        returncode=process.returncode or 0,
        # `errors="replace"` e non `strict`: un SSID può contenere byte che non sono UTF-8
        # valido, e non è una buona ragione per far fallire una scansione.
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )
    if not result.ok:
        logger.debug(
            "%s → codice %s: %s", " ".join(command), result.returncode, result.stderr.strip()
        )
    return result
