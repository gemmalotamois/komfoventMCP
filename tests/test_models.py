from komfovent_mcp.models import (
    build_alarms,
    build_energy,
    build_status,
    decode_controller_firmware,
    decode_panel_firmware,
    temperature_word,
)
from komfovent_mcp.errors import KomfoventError
import pytest


def test_c8_firmware_word_from_the_live_unit() -> None:
    controller, version = decode_controller_firmware(0x1153204D)
    assert controller == "c8"
    assert version == "1.1.5.50.77"


def test_c6_firmware_example_from_the_manual() -> None:
    controller, version = decode_controller_firmware(18_886_660)
    assert controller == "c6"
    assert version == "1.2.3.4"


def test_panel_firmware() -> None:
    assert decode_panel_firmware((272 << 16) + 20533) == "1.1.5.53"
    assert decode_panel_firmware(18_886_660) == "1.2.3.4"
    assert decode_panel_firmware(0) is None


def test_temperature_limits() -> None:
    assert temperature_word(21.5) == 215
    assert temperature_word(5) == 50
    assert temperature_word(40) == 400
    with pytest.raises(KomfoventError):
        temperature_word(4.9)
    with pytest.raises(KomfoventError):
        temperature_word(40.1)


def test_status_decodes_the_probed_c8_image() -> None:
    raw = {
        1: 1,
        3: 0,
        4: 0,
        5: 7,
        12: 3,
        28: 0,
        142: 245,
        206: 200,
        900: 44,
        901: 3,
        902: 192,
        903: 225,
        904: 47,
        905: 192,
        906: 0,
        907: 95,
        908: 0,
        909: 100,
        910: 950,
        911: 1000,
        912: 1000,
        915: 1000,
        917: 50,
        919: 8,
        921: 176,
        946: 245,
        947: 28,
        954: 1,
        955: 0,
        956: 626,
        957: 65535,
        961: 102,
        1000: 4435,
        1001: 8269,
        1002: 272,
        1003: 20533,
    }
    status = build_status(raw, host="192.168.0.60", unit_id=1)
    assert status["power"] is True
    assert status["mode"] == "override"
    assert status["eco"] is False
    assert status["auto"] is False
    assert status["controller"] == "c8"
    assert status["firmware"] == "1.1.5.50.77"
    assert status["panel1_firmware"] == "1.1.5.53"
    assert status["panel2_firmware"] is None
    assert status["setpoint_c"] == 24.5
    assert status["air_quality_setpoint_c"] == 20.0
    assert status["flow_control"] == "off"
    assert status["temperatures_c"]["supply"] == 19.2
    assert status["temperatures_c"]["extract"] == 22.5
    assert status["temperatures_c"]["outdoor"] == 4.7
    assert status["temperatures_c"]["room"] == 24.5
    assert status["temperatures_c"]["exhaust"] == 10.2
    assert status["flows"] == {"supply": 95, "extract": 100, "unit": "m3/h"}
    assert status["fans_percent"] == {"supply": 95.0, "extract": 100.0}
    assert status["filter_impurity_percent"] == 50
    assert status["power_w"] == 176
    assert status["status"] == ["fan", "rotor", "cooling"]
    assert status["heating"] == ["electric_heater", "water_coil"]
    assert status["heat_exchanger"] == "plate"
    assert status["panels"] == ["panel1"]
    assert status["humidity"]["panel1_percent"] == 28
    assert status["humidity"]["indoor_g_m3"] == 6.26
    assert status["humidity"]["outdoor_g_m3"] is None


def test_missing_sensor_is_absent_not_zero() -> None:
    status = build_status({}, host="192.168.0.60", unit_id=1)
    assert status["temperatures_c"]["supply"] is None
    assert status["power"] is None


def test_alarm_text() -> None:
    assert build_alarms({600: 0}) == {"count": 0, "alarms": []}
    decoded = build_alarms({600: 2, 601: 1, 602: 129})
    assert decoded["count"] == 2
    assert decoded["alarms"][0]["label"] == "F1"
    assert decoded["alarms"][0]["severity"] == "fault"
    assert decoded["alarms"][1] == {
        "code": 129,
        "label": "W1",
        "message": "Change air filter",
        "severity": "warning",
    }


def test_energy_word_order_matches_the_panel() -> None:
    raw = {
        921: 176,
        922: 0,
        923: 1476,
        924: 83,
        925: 100,
        926: 572,
        927: 0,
        928: 1036,
        929: 1,
        930: 4047,
        931: 48,
        932: 3201,
        933: 0,
        934: 0,
        935: 0,
        936: 18196,
        937: 23,
        938: 53480,
        939: 0,
        940: 12061,
        941: 7,
        942: 36242,
        943: 52,
        944: 9130,
        945: 372,
    }
    energy = build_energy(raw)
    assert energy["power_w"] == 176
    assert energy["heat_recovery_w"] == 1476
    assert energy["heat_exchanger_efficiency_percent"] == 83
    assert energy["specific_power_w_per_m3h"] == 0.572
    assert energy["specific_power_day_w_per_m3h"] == 0.372
    assert energy["ahu_wh"]["day"] == 1036
    assert energy["ahu_wh"]["month"] == 69583
    assert energy["ahu_wh"]["total"] == 3_148_929
    assert energy["heater_wh"]["total"] == 1_560_808
    assert energy["recovered_wh"]["day"] == 12061
    assert energy["recovered_wh"]["month"] == 494994
    assert energy["recovered_wh"]["total"] == 3_417_002
