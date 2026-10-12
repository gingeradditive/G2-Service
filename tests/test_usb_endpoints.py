"""Contratto degli endpoint della chiavetta USB (docs 07).

Il mock usa la logica reale e cambia solo il criterio di presenza (la cartella `media_dir`
esiste), quindi qui si verificano davvero filtri, percorsi e copia, su `tmp_path`.
"""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_PREFIX = "/service/usb"


@pytest.fixture
def media(tmp_path: Path) -> Path:
    """Una chiavetta "inserita" con un po' di tutto, e la radice `gcodes` già creata."""
    root = tmp_path / "media"
    (root / "lavori" / "aprile").mkdir(parents=True)
    (root / "System Volume Information").mkdir()
    (root / ".Trashes").mkdir()
    (root / "vaso.gcode").write_text("G28\n")
    (root / "Base.GCODE").write_text("G28\n")
    (root / "modello.stl").write_text("solid")
    (root / ".nascosto.gcode").write_text("G28\n")
    (root / "lavori" / "pezzo.gcode").write_text("G1 X10\n")
    (tmp_path / "printer_data" / "gcodes" / "sotto").mkdir(parents=True)
    return root


def _gcodes(tmp_path: Path) -> Path:
    return tmp_path / "printer_data" / "gcodes"


def _wait_job(client: TestClient, job_id: str, *, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/service/jobs/{job_id}").json()
        if body["status"] != "running":
            return body
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} non concluso entro {timeout}s")


def _import(client: TestClient, **body) -> dict:
    response = client.post(f"{_PREFIX}/import", json=body)
    assert response.status_code == 202, response.json()
    return _wait_job(client, response.json()["jobId"])


def test_status_senza_chiavetta(client: TestClient):
    assert client.get(_PREFIX).json() == {"mounted": False}


def test_status_con_chiavetta(client: TestClient, media: Path):
    assert client.get(_PREFIX).json() == {"mounted": True}


def test_files_senza_chiavetta_409(client: TestClient):
    response = client.get(f"{_PREFIX}/files")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "USB_NOT_MOUNTED"


def test_files_radice_filtrata_e_ordinata(client: TestClient, media: Path):
    body = client.get(f"{_PREFIX}/files").json()
    assert body["path"] == ""
    assert [d["name"] for d in body["dirs"]] == ["lavori"]
    assert [f["name"] for f in body["files"]] == ["Base.GCODE", "vaso.gcode"]
    assert {"name", "size", "modified"} <= body["files"][0].keys()


def test_files_sottocartella(client: TestClient, media: Path):
    body = client.get(f"{_PREFIX}/files", params={"path": "lavori"}).json()
    assert body["path"] == "lavori"
    assert [d["name"] for d in body["dirs"]] == ["aprile"]
    assert [f["name"] for f in body["files"]] == ["pezzo.gcode"]


def test_files_cartella_inesistente_404(client: TestClient, media: Path):
    response = client.get(f"{_PREFIX}/files", params={"path": "non-esiste"})
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["..", "lavori/../..", "/etc"])
def test_files_fuori_dalla_chiavetta_400(client: TestClient, media: Path, path: str):
    response = client.get(f"{_PREFIX}/files", params={"path": path})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_INPUT"


def test_files_symlink_che_esce_400(client: TestClient, media: Path, tmp_path: Path):
    (media / "fuga").symlink_to(tmp_path)
    response = client.get(f"{_PREFIX}/files", params={"path": "fuga"})
    assert response.status_code == 400


def test_import_nella_radice(client: TestClient, media: Path, tmp_path: Path):
    job = _import(client, source="vaso.gcode")
    assert job["status"] == "succeeded"
    assert job["result"] == {"filename": "vaso.gcode", "path": "vaso.gcode"}
    imported = _gcodes(tmp_path) / "vaso.gcode"
    assert imported.read_text() == "G28\n"
    assert imported.stat().st_mode & 0o777 == 0o644
    # Niente `.part` rimasti in giro.
    assert list((tmp_path / "printer_data" / ".g2-import").iterdir()) == []


def test_import_in_sottocartella(client: TestClient, media: Path, tmp_path: Path):
    job = _import(client, source="lavori/pezzo.gcode", destDir="sotto")
    assert job["result"] == {"filename": "pezzo.gcode", "path": "sotto/pezzo.gcode"}
    assert (_gcodes(tmp_path) / "sotto" / "pezzo.gcode").is_file()


def test_import_conflitto_fail_409_subito(client: TestClient, media: Path, tmp_path: Path):
    (_gcodes(tmp_path) / "vaso.gcode").write_text("vecchio")
    response = client.post(f"{_PREFIX}/import", json={"source": "vaso.gcode"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "FILE_EXISTS"
    assert (_gcodes(tmp_path) / "vaso.gcode").read_text() == "vecchio"


def test_import_conflitto_overwrite(client: TestClient, media: Path, tmp_path: Path):
    (_gcodes(tmp_path) / "vaso.gcode").write_text("vecchio")
    job = _import(client, source="vaso.gcode", onConflict="overwrite")
    assert job["result"]["filename"] == "vaso.gcode"
    assert (_gcodes(tmp_path) / "vaso.gcode").read_text() == "G28\n"


def test_import_conflitto_rename(client: TestClient, media: Path, tmp_path: Path):
    (_gcodes(tmp_path) / "vaso.gcode").write_text("vecchio")
    (_gcodes(tmp_path) / "vaso (1).gcode").write_text("vecchio 1")
    job = _import(client, source="vaso.gcode", onConflict="rename")
    assert job["result"] == {"filename": "vaso (2).gcode", "path": "vaso (2).gcode"}
    assert (_gcodes(tmp_path) / "vaso.gcode").read_text() == "vecchio"
    assert (_gcodes(tmp_path) / "vaso (2).gcode").read_text() == "G28\n"


def test_import_file_non_stampabile_400(client: TestClient, media: Path):
    response = client.post(f"{_PREFIX}/import", json={"source": "modello.stl"})
    assert response.status_code == 400


def test_import_sorgente_inesistente_404(client: TestClient, media: Path):
    response = client.post(f"{_PREFIX}/import", json={"source": "manca.gcode"})
    assert response.status_code == 404


def test_import_destinazione_inesistente_404(client: TestClient, media: Path):
    response = client.post(
        f"{_PREFIX}/import", json={"source": "vaso.gcode", "destDir": "non-esiste"}
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"source": "../printer_data/gcodes/x.gcode"},
        {"source": "vaso.gcode", "destDir": "../config"},
        {"source": "vaso.gcode", "destDir": "/tmp"},
    ],
)
def test_import_percorsi_fuori_radice_400(client: TestClient, media: Path, body: dict):
    response = client.post(f"{_PREFIX}/import", json=body)
    assert response.status_code == 400


def test_import_senza_chiavetta_409(client: TestClient):
    response = client.post(f"{_PREFIX}/import", json={"source": "vaso.gcode"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "USB_NOT_MOUNTED"
