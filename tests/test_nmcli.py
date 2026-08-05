"""Parsing dell'output `nmcli` (docs 05 — Test e qualità).

Copre i casi in cui il formato tabellare tradisce chi lo legge con `str.split(":")`: SSID e MAC
coi due punti dentro, campi vuoti (`--`), stati scritti in forme diverse a seconda del comando.
"""

from datetime import datetime, timezone

from src.models.network import InterfaceState
from src.services.network.nmcli import (
    indexed_values,
    parse_access_points,
    parse_bool,
    parse_detail,
    parse_devices,
    parse_state,
    parse_timestamp,
    split_terse,
)

# --------------------------------------------------------------------------- split_terse


def test_split_terse_semplice():
    assert split_terse("wlan0:wifi:connected:Ginger-Lab") == [
        "wlan0",
        "wifi",
        "connected",
        "Ginger-Lab",
    ]


def test_split_terse_due_punti_protetti_nel_valore():
    # Un MAC address, o un SSID che contiene ':', arriva con i due punti protetti da `\`.
    assert split_terse(r"b8\:27\:eb\:1a\:2b\:3c") == ["b8:27:eb:1a:2b:3c"]


def test_split_terse_ssid_con_due_punti():
    assert split_terse(r"*:80:WPA2:2412:Lab\:Ufficio", maxsplit=4) == [
        "*",
        "80",
        "WPA2",
        "2412",
        "Lab:Ufficio",
    ]


def test_split_terse_campo_vuoto():
    assert split_terse("wlan0:wifi::") == ["wlan0", "wifi", "", ""]


def test_split_terse_maxsplit_limita_le_separazioni():
    # Oltre `maxsplit` separazioni, i `:` restanti restano nell'ultimo campo anche se non
    # protetti: è la garanzia che tiene in piedi il parsing quando una versione di `nmcli`
    # dimentica di proteggere un valore.
    assert split_terse("a:b:c:d:e", maxsplit=2) == ["a", "b", "c:d:e"]


# --------------------------------------------------------------------------- parse_state


def test_parse_state_forma_device_status():
    assert parse_state("connected") == InterfaceState.CONNECTED
    assert parse_state("disconnected") == InterfaceState.DISCONNECTED


def test_parse_state_forma_device_show():
    assert parse_state("100 (connected)") == InterfaceState.CONNECTED
    assert parse_state("20 (unavailable)") == InterfaceState.UNAVAILABLE


def test_parse_state_connessione_in_corso():
    assert parse_state("connecting (getting IP configuration)") == InterfaceState.CONNECTING


def test_parse_state_deactivating_e_failed_sono_disconnected():
    assert parse_state("deactivating") == InterfaceState.DISCONNECTED
    assert parse_state("failed") == InterfaceState.DISCONNECTED


def test_parse_state_sconosciuto_non_solleva():
    assert parse_state("qualcosa-di-nuovo") == InterfaceState.UNKNOWN


def test_parse_state_case_insensitive():
    assert parse_state("CONNECTED") == InterfaceState.CONNECTED


# --------------------------------------------------------------------------- parse_devices


def test_parse_devices_righe_multiple():
    stdout = "wlan0:wifi:connected:Ginger-Lab\neth0:ethernet:unavailable:\n"
    devices = parse_devices(stdout)
    assert len(devices) == 2
    assert devices[0].device == "wlan0"
    assert devices[0].connection == "Ginger-Lab"
    assert devices[1].connection is None  # campo vuoto


def test_parse_devices_placeholder_doppio_trattino_e_vuoto():
    for empty in ("", "--"):
        [device] = parse_devices(f"wlan0:wifi:connected:{empty}")
        assert device.connection is None


def test_parse_devices_riga_malformata_viene_scartata():
    stdout = "wlan0:wifi:connected:Ginger-Lab\nriga-corta:wifi\n"
    devices = parse_devices(stdout)
    assert len(devices) == 1


def test_parse_devices_righe_vuote_ignorate():
    stdout = "\nwlan0:wifi:connected:Ginger-Lab\n\n"
    assert len(parse_devices(stdout)) == 1


# ----------------------------------------------------------------------- parse_access_points


def test_parse_access_points_campi_base():
    stdout = "*:80:WPA2:2412:Ginger-Lab"
    [ap] = parse_access_points(stdout)
    assert ap.ssid == "Ginger-Lab"
    assert ap.signal == 80
    assert ap.security == "WPA2"
    assert ap.frequency == 2412
    assert ap.in_use is True


def test_parse_access_points_rete_aperta_ha_security_open():
    [ap] = parse_access_points(":45:::Ospiti")
    assert ap.security == "open"


def test_parse_access_points_ssid_nascosto_e_vuoto():
    [ap] = parse_access_points(":30:WPA2:2437:")
    assert ap.ssid == ""
    assert ap.is_hidden is True


def test_parse_access_points_ssid_con_due_punti_non_spezza_i_campi():
    stdout = r"*:60:WPA2:5180:Sala\:Riunioni"
    [ap] = parse_access_points(stdout)
    assert ap.ssid == "Sala:Riunioni"
    assert ap.signal == 60
    assert ap.frequency == 5180


def test_parse_access_points_freq_con_unita_di_misura():
    # `FREQ` a volte arriva come "2412 MHz" e non come numero nudo.
    [ap] = parse_access_points("*:50:WPA2:2412 MHz:Rete")
    assert ap.frequency == 2412


def test_parse_access_points_riga_malformata_viene_scartata():
    stdout = "*:80:WPA2:2412:Ginger-Lab\ntroppo:corta\n"
    assert len(parse_access_points(stdout)) == 1


def test_parse_access_points_in_use_solo_con_asterisco():
    [ap] = parse_access_points(":80:WPA2:2412:Rete")
    assert ap.in_use is False


# --------------------------------------------------------------------------- parse_detail


def test_parse_detail_coppie_chiave_valore():
    stdout = "GENERAL.DEVICE:wlan0\nGENERAL.HWADDR:B8\\:27\\:EB\\:1A\\:2B\\:3C\n"
    detail = parse_detail(stdout)
    assert detail["GENERAL.DEVICE"] == "wlan0"
    assert detail["GENERAL.HWADDR"] == "B8:27:EB:1A:2B:3C"


def test_indexed_values_ordine_e_arresto():
    detail = {
        "IP4.ADDRESS[1]": "192.168.1.42/24",
        "IP4.ADDRESS[2]": "192.168.1.43/24",
    }
    assert indexed_values(detail, "IP4.ADDRESS") == [
        "192.168.1.42/24",
        "192.168.1.43/24",
    ]


def test_indexed_values_nessun_valore():
    assert indexed_values({}, "IP4.ADDRESS") == []


def test_indexed_values_placeholder_vuoto_interrompe_la_sequenza():
    detail = {"IP4.ADDRESS[1]": "--", "IP4.ADDRESS[2]": "192.168.1.43/24"}
    # Un buco nella sequenza non dovrebbe capitare, ma se capita ci si ferma: non si salta
    # un indice per andare a cercare oltre.
    assert indexed_values(detail, "IP4.ADDRESS") == []


# ------------------------------------------------------------------------ parse_timestamp


def test_parse_timestamp_epoch_valido():
    assert parse_timestamp("1700000000") == datetime.fromtimestamp(1700000000, tz=timezone.utc)


def test_parse_timestamp_zero_vuol_dire_mai_usata():
    assert parse_timestamp("0") is None


def test_parse_timestamp_none_o_vuoto():
    assert parse_timestamp(None) is None
    assert parse_timestamp("") is None
    assert parse_timestamp("   ") is None


def test_parse_timestamp_non_numerico():
    assert parse_timestamp("non-un-numero") is None


# ------------------------------------------------------------------------------ parse_bool


def test_parse_bool_yes_no():
    assert parse_bool("yes") is True
    assert parse_bool("no") is False
    assert parse_bool(None) is False
    assert parse_bool("") is False
    assert parse_bool("YES") is True
