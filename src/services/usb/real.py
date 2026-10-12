"""Implementazione reale di `UsbService`: filesystem puro (docs 07).

La chiavetta è montata in sola lettura su `media_dir` da G2-OS (pmount, modulo
`61-EnableUSB`). Qui non si monta né si smonta niente: si legge e si copia in `gcodes`.

Ogni accesso al filesystem gira in un thread: una chiavetta lenta, o una che è appena stata
tolta, può bloccare una `read` per secondi, e l'event loop serve anche a tutto il resto.
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from src.errors import (
    InvalidInputError,
    JobFailure,
    NotFoundError,
    TargetExistsError,
    UsbNotMountedError,
    UsbReadError,
)
from src.models.usb import OnConflict, UsbDir, UsbDirectory, UsbFile, UsbStatus
from src.services.jobs import JobFunc
from src.settings import Settings

logger = logging.getLogger(__name__)

#: Gli unici file che GingerView sa stampare. Il resto della chiavetta non si mostra nemmeno.
PRINTABLE_SUFFIXES = frozenset({".gcode"})

# Cartelle che Windows lascia su ogni chiavetta. Quelle di macOS (`.Trashes`,
# `.Spotlight-V100`, `.fseventsd`) sono già escluse in quanto nascoste.
_SYSTEM_DIRS = frozenset({"system volume information", "$recycle.bin"})

# Cartella di appoggio della copia, accanto a `gcodes` e quindi sullo stesso filesystem
# (`os.replace` è atomico solo lì), ma fuori dalle radici di Moonraker.
IMPORT_TMP_DIRNAME = ".g2-import"

_CHUNK_SIZE = 1024 * 1024


class FilesystemUsbService:
    def __init__(self, settings: Settings) -> None:
        self._media_dir = settings.media_dir
        self._gcodes_dir = settings.gcodes_dir
        self._tmp_dir = settings.printer_data_dir / IMPORT_TMP_DIRNAME
        # Un `.part` rimasto qui è di un import interrotto da un riavvio: allo startup nessun
        # job è in corso, quindi si può buttare tutto.
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _is_mounted(self) -> bool:
        return os.path.ismount(self._media_dir)

    async def status(self) -> UsbStatus:
        return UsbStatus(mounted=await asyncio.to_thread(self._is_mounted))

    async def list_dir(self, path: str) -> UsbDirectory:
        await self._ensure_mounted()
        root = self._media_dir.resolve()
        directory = resolve_inside(root, path)
        return await asyncio.to_thread(_scan, root, directory)

    async def prepare_import(self, source: str, dest_dir: str, on_conflict: OnConflict) -> JobFunc:
        await self._ensure_mounted()
        src = resolve_inside(self._media_dir.resolve(), source)
        if not is_printable(src.name):
            raise InvalidInputError(f"Non è un file stampabile: {source}")
        if not await asyncio.to_thread(src.is_file):
            raise NotFoundError(f"File non trovato sulla chiavetta: {source}")

        gcodes = self._gcodes_dir.resolve()
        dest = resolve_inside(gcodes, dest_dir)
        if not dest.is_dir():
            raise NotFoundError(f"Cartella di destinazione inesistente: {dest_dir or '/'}")
        if on_conflict is OnConflict.FAIL and (dest / src.name).exists():
            raise TargetExistsError(f"Esiste già {src.name} in {dest_dir or '/'}")

        async def run() -> dict[str, Any]:
            return await asyncio.to_thread(self._copy, src, dest, on_conflict)

        return run

    async def _ensure_mounted(self) -> None:
        if not await asyncio.to_thread(self._is_mounted):
            raise UsbNotMountedError()

    def _copy(self, src: Path, dest: Path, on_conflict: OnConflict) -> dict[str, Any]:
        target = dest / src.name
        # Il conflitto si ricontrolla: fra il `202` e questo punto il file può essere comparso.
        if target.exists():
            if on_conflict is OnConflict.FAIL:
                raise JobFailure("FILE_EXISTS", f"Esiste già {src.name}")
            if on_conflict is OnConflict.RENAME:
                target = free_name(dest, src.name)

        self._tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._tmp_dir / f"{uuid4().hex}.part"
        try:
            _copy_contents(src, tmp)
            self._finalize(tmp)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

        relative = target.relative_to(self._gcodes_dir.resolve()).as_posix()
        logger.info("Importato %s → gcodes/%s", src, relative)
        return {"filename": target.name, "path": relative}

    def _finalize(self, tmp: Path) -> None:
        """Permessi e proprietario come quelli di un file caricato da Moonraker.

        Il servizio gira come root: senza `chown` il file in `gcodes` sarebbe di root, e
        Moonraker (utente `pi`) non potrebbe più rinominarlo né cancellarlo.
        """
        os.chmod(tmp, 0o644)
        if os.geteuid() == 0:
            owner = self._gcodes_dir.stat()
            os.chown(tmp, owner.st_uid, owner.st_gid)


def is_printable(name: str) -> bool:
    return PurePosixPath(name).suffix.lower() in PRINTABLE_SUFFIXES


def resolve_inside(root: Path, raw: str) -> Path:
    """Risolve un percorso relativo dentro `root` (già risolta) e verifica che ci resti.

    Il controllo sui `..` precede la risoluzione e quello su `is_relative_to` la segue: il
    primo rifiuta l'intenzione, il secondo copre i symlink che puntano fuori.
    """
    relative = PurePosixPath(raw.strip())
    if relative.is_absolute() or ".." in relative.parts:
        raise InvalidInputError(f"Percorso non valido: {raw}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise InvalidInputError(f"Percorso non valido: {raw}")
    return target


def free_name(directory: Path, name: str) -> Path:
    """`vaso.gcode` → `vaso (1).gcode`, `vaso (2).gcode`, … il primo che non esiste."""
    stem, suffix = PurePosixPath(name).stem, PurePosixPath(name).suffix
    n = 1
    while (candidate := directory / f"{stem} ({n}){suffix}").exists():
        n += 1
    return candidate


def _scan(root: Path, directory: Path) -> UsbDirectory:
    if not directory.is_dir():
        raise NotFoundError(f"Cartella non trovata sulla chiavetta: {directory.name}")
    dirs: list[UsbDir] = []
    files: list[UsbFile] = []
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                # Niente symlink seguiti: su una chiavetta ext4 potrebbero puntare fuori, o
                # formare un ciclo.
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.lower() not in _SYSTEM_DIRS:
                        dirs.append(UsbDir(name=entry.name))
                elif entry.is_file(follow_symlinks=False) and is_printable(entry.name):
                    stat = entry.stat(follow_symlinks=False)
                    files.append(
                        UsbFile(
                            name=entry.name,
                            size=stat.st_size,
                            modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
                        )
                    )
    except OSError as exc:
        raise UsbReadError(f"Lettura della chiavetta non riuscita: {exc.strerror}") from exc

    relative = directory.relative_to(root).as_posix()
    return UsbDirectory(
        path="" if relative == "." else relative,
        dirs=sorted(dirs, key=lambda d: d.name.lower()),
        files=sorted(files, key=lambda f: f.name.lower()),
    )


def _copy_contents(src: Path, tmp: Path) -> None:
    """Copia a blocchi, distinguendo chi ha fallito: la chiavetta o la memoria interna.

    Per l'utente sono due cose diverse — "reinserisci la chiavetta" contro "libera spazio" — e
    `shutil.copyfileobj` le confonderebbe in un solo `OSError`.
    """
    try:
        fin = src.open("rb")
    except OSError as exc:
        raise JobFailure("USB_READ_ERROR", f"Chiavetta non leggibile: {exc.strerror}") from exc
    with fin:
        try:
            with tmp.open("wb") as fout:
                while True:
                    try:
                        chunk = fin.read(_CHUNK_SIZE)
                    except OSError as exc:
                        raise JobFailure(
                            "USB_READ_ERROR", f"Lettura interrotta: {exc.strerror}"
                        ) from exc
                    if not chunk:
                        break
                    fout.write(chunk)
                fout.flush()
                # Prima dello spostamento: dopo un'interruzione di corrente il file in `gcodes`
                # deve essere intero o non esserci.
                os.fsync(fout.fileno())
        except OSError as exc:
            message = f"Scrittura nella memoria interna non riuscita: {exc.strerror}"
            raise JobFailure("STORAGE_WRITE_ERROR", message) from exc
