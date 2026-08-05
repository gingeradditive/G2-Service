"""Contratto degli endpoint di rete, verificato attraverso il livello mock (docs 05 — Test e
qualità, docs 03).

Non riverifica la logica del mock stesso (sta in `services/network/mock.py`): controlla la
forma delle risposte che GingerView consuma — status code, `camelCase`, forma degli errori — e
i tre scenari di fallimento selezionabili con `G2_SERVICE_MOCK_SCENARIO`.
"""

import time

from fastapi.testclient import TestClient

from src.mock_scenarios import MockScenario

_PREFIX = "/service/network"


def _wait_job(client: TestClient, job_id: str, *, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/service/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] != "running":
            return body
        time.sleep(0.1)
    raise AssertionError(f"Job {job_id} non concluso entro {timeout}s")


def test_status_e_camel_case(client: TestClient):
    response = client.get(f"{_PREFIX}/status")
    assert response.status_code == 200
    body = response.json()
    assert "adapter" in body
    assert "signalInfo" in body  # non "signal_info": il contratto è camelCase
    assert body["adapter"]["state"] in {
        "connected",
        "connecting",
        "disconnected",
        "unavailable",
        "unmanaged",
        "unknown",
    }


def test_wifi_networks_lista_non_vuota_di_default(client: TestClient):
    response = client.get(f"{_PREFIX}/wifi/networks")
    assert response.status_code == 200
    networks = response.json()
    assert len(networks) > 0
    assert {"ssid", "signalStrength", "security", "isHidden"} <= networks[0].keys()


def test_wifi_rescan_restituisce_elenco_aggiornato(client: TestClient):
    response = client.post(f"{_PREFIX}/wifi/rescan")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_saved_networks(client: TestClient):
    response = client.get(f"{_PREFIX}/wifi/saved")
    assert response.status_code == 200
    saved = response.json()
    assert len(saved) > 0
    assert {"ssid", "autoconnect"} <= saved[0].keys()


def test_ethernet_status(client: TestClient):
    response = client.get(f"{_PREFIX}/ethernet/status")
    assert response.status_code == 200
    body = response.json()
    assert {"device", "cableConnected", "state", "ip"} <= body.keys()


def test_forget_saved_network_inesistente_e_404_con_error_model(client: TestClient):
    response = client.delete(f"{_PREFIX}/wifi/saved/rete-mai-esistita")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["code"] == "NOT_FOUND"


def test_forget_saved_network_esistente(client: TestClient):
    response = client.delete(f"{_PREFIX}/wifi/saved/Ginger-Lab")
    assert response.status_code == 204


def test_wifi_connect_e_un_job_202(client: TestClient):
    response = client.post(f"{_PREFIX}/wifi/connect", json={"ssid": "Ginger-Lab"})
    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "running"
    assert job["jobId"]

    finished = _wait_job(client, job["jobId"])
    assert finished["status"] == "succeeded"
    assert finished["result"]["ssid"] == "Ginger-Lab"


def test_wifi_connect_ssid_non_in_scansione_fallisce_come_job_non_come_errore_http(
    client: TestClient,
):
    response = client.post(f"{_PREFIX}/wifi/connect", json={"ssid": "Rete-Inventata"})
    assert response.status_code == 202  # accettata: l'esito negativo arriva nel job

    finished = _wait_job(client, response.json()["jobId"])
    assert finished["status"] == "failed"
    assert finished["error"]["code"] == "WIFI_NETWORK_NOT_FOUND"


def test_wifi_connect_due_volte_di_seguito_e_conflitto(client: TestClient):
    first = client.post(f"{_PREFIX}/wifi/connect", json={"ssid": "Ginger-Lab"})
    assert first.status_code == 202

    second = client.post(f"{_PREFIX}/wifi/connect", json={"ssid": "Officina"})
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "CONFLICT"


def test_wifi_connect_ssid_vuoto_e_validazione_422(client: TestClient):
    response = client.post(f"{_PREFIX}/wifi/connect", json={"ssid": ""})
    assert response.status_code == 422


def test_wifi_disconnect_e_un_job(client: TestClient):
    response = client.post(f"{_PREFIX}/wifi/disconnect")
    assert response.status_code == 202
    finished = _wait_job(client, response.json()["jobId"])
    assert finished["status"] == "succeeded"


# --------------------------------------------------------------------- scenari di fallimento


def test_scenario_wrong_password(make_client):
    with make_client(MockScenario.WRONG_PASSWORD) as scenario_client:
        response = scenario_client.post(
            f"{_PREFIX}/wifi/connect", json={"ssid": "Ginger-Lab", "password": "qualsiasi"}
        )
        assert response.status_code == 202
        finished = _wait_job(scenario_client, response.json()["jobId"])
        assert finished["status"] == "failed"
        assert finished["error"]["code"] == "WIFI_AUTH_FAILED"


def test_scenario_no_networks(make_client):
    with make_client(MockScenario.NO_NETWORKS) as scenario_client:
        response = scenario_client.get(f"{_PREFIX}/wifi/networks")
        assert response.status_code == 200
        assert response.json() == []


def test_scenario_nm_unavailable(make_client):
    with make_client(MockScenario.NM_UNAVAILABLE) as scenario_client:
        response = scenario_client.get(f"{_PREFIX}/status")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "SYSTEM_TOOL_UNAVAILABLE"
