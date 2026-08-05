"""Fixture condivise per i test degli endpoint (docs 05 — Test e qualità).

Girano sempre contro il livello mock: `Settings` è costruito a mano invece che con
`Settings.from_env()`, così ogni test controlla `mock_scenario` senza dipendere da variabili
d'ambiente o dalla piattaforma su cui gira `pytest`.
"""

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.mock_scenarios import MockScenario
from src.settings import Settings


@pytest.fixture
def make_client(tmp_path) -> Callable[[MockScenario | None], TestClient]:
    """Fabbrica di `TestClient`, uno scenario mock diverso per ogni chiamata."""

    def _make(mock_scenario: MockScenario | None = None) -> TestClient:
        settings = Settings(
            host="127.0.0.1",
            port=8000,
            mock=True,
            mock_scenario=mock_scenario,
            etc_dir=tmp_path / "etc" / "g2",
            printer_data_dir=tmp_path / "printer_data",
        )
        return TestClient(create_app(settings))

    return _make


@pytest.fixture
def client(make_client: Callable[[MockScenario | None], TestClient]) -> Iterator[TestClient]:
    with make_client() as test_client:
        yield test_client
