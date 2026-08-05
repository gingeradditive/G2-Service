"""Scenari di fallimento selezionabili in modalità mock (`G2_SERVICE_MOCK_SCENARIO`, docs 05).

Servono a sviluppare i casi che rompono l'interfaccia — password sbagliata, nessuna rete
trovata, NetworkManager assente — senza una macchina reale sul banco. Il valore è unico per
tutto il processo: non ha senso avere scenari diversi per endpoint diversi nella stessa sessione
di sviluppo.
"""

from enum import Enum


class MockScenario(str, Enum):
    WRONG_PASSWORD = "wrong-password"
    NO_NETWORKS = "no-networks"
    NM_UNAVAILABLE = "nm-unavailable"


def parse_mock_scenario(raw: str | None) -> "MockScenario | None":
    if raw is None or not raw.strip():
        return None
    value = raw.strip().lower()
    try:
        return MockScenario(value)
    except ValueError:
        valid = ", ".join(scenario.value for scenario in MockScenario)
        raise ValueError(f"Scenario mock non riconosciuto: {raw!r} (validi: {valid})") from None
