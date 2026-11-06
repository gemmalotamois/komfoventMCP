import time

import pytest

from komfovent_mcp.client import KomfoventClient
from komfovent_mcp.config import Config
from komfovent_mcp.errors import KomfoventError
from tests.fake_modbus import FakeModbus


def client(store=None, **kwargs) -> tuple[KomfoventClient, FakeModbus]:
    modbus = FakeModbus(store, **kwargs)
    config = Config(host="192.168.0.60", port=502, unit_id=1, timeout=1, min_gap_s=0)
    return KomfoventClient(config, modbus=modbus), modbus


async def test_reads_use_zero_based_addresses_and_unit_id() -> None:
    unit, modbus = client()
    unit.config = Config("192.168.0.60", 502, unit_id=7, timeout=1, min_gap_s=0)
    await unit.get_alarms()
    assert modbus.reads == [(599, 11, 7)]
    assert modbus.connects == 1


async def test_transactions_wait_for_the_minimum_gap() -> None:
    unit, _modbus = client()
    unit.config = Config("192.168.0.60", unit_id=1, timeout=1, min_gap_s=0.05)
    await unit.get_alarms()
    started = time.monotonic()
    await unit.get_alarms()
    assert time.monotonic() - started >= 0.05


async def test_connection_loss_is_retried_once() -> None:
    unit, modbus = client(failures=1)
    await unit.get_alarms()
    assert modbus.connects == 2
    assert len(modbus.reads) == 1


async def test_set_temperature_writes_override_and_air_quality_setpoints() -> None:
    unit, modbus = client({5: 7})
    status = await unit.set_temperature(21.5)
    assert ("one", 141, 215, 1) in modbus.writes
    assert ("one", 205, 215, 1) in modbus.writes
    assert status["mode"] == "override"
    assert status["setpoint_c"] == 21.5
    assert status["air_quality_setpoint_c"] == 21.5


async def test_air_quality_mode_writes_register_206_once() -> None:
    unit, modbus = client({5: 9})
    await unit.set_temperature(20)
    temperature_writes = [write for write in modbus.writes if write[1] == 205]
    assert temperature_writes == [("one", 205, 200, 1)]


async def test_set_mode_rejects_modes_the_controller_will_not_accept() -> None:
    unit, modbus = client()
    with pytest.raises(KomfoventError):
        await unit.set_mode("kitchen")
    assert modbus.writes == []


async def test_set_power_and_filter_reset_addresses() -> None:
    unit, modbus = client()
    await unit.set_power(False)
    await unit.reset_filters()
    assert ("one", 0, 0, 1) in modbus.writes
    assert ("one", 1050, 1, 1) in modbus.writes
    assert all(write[1] != 1049 for write in modbus.writes)


async def test_settings_reset_register_is_rejected() -> None:
    unit, modbus = client()
    with pytest.raises(KomfoventError):
        await unit._write_u16(1050, 1)
    assert modbus.writes == []


async def test_signed_write_uses_twos_complement() -> None:
    unit, modbus = client()
    await unit._write_i16(104, -10)
    assert modbus.writes == [("one", 103, 65526, 1)]


async def test_mode_settings_split_a_32_bit_flow() -> None:
    unit, modbus = client({5: 2})
    await unit.set_mode_settings(
        "normal",
        supply_flow=200,
        extract_flow=180,
        setpoint_c=21,
        heating=True,
    )
    assert ("many", 105, [0, 200], 1) in modbus.writes
    assert ("many", 107, [0, 180], 1) in modbus.writes
    assert ("one", 109, 210, 1) in modbus.writes
    assert ("one", 110, 1, 1) in modbus.writes


async def test_holiday_flow_is_rejected_before_any_write() -> None:
    unit, modbus = client()
    with pytest.raises(KomfoventError):
        await unit.set_mode_settings("holiday", supply_flow=100)
    assert modbus.writes == []


async def test_alarm_reset_writes_the_documented_code() -> None:
    unit, modbus = client()
    result = await unit.reset_alarms()
    assert ("one", 599, 0x99C6, 1) in modbus.writes
    # The stand-in echoes the written register, so the following read still shows it.
    assert result["count"] == 0x99C6


async def test_missing_panel_2_does_not_fail_status() -> None:
    unit, modbus = client({5: 7, 954: 3}, illegal={1003})
    status = await unit.get_status()
    assert status["panels"] == ["panel1", "panel2"]
    assert status["panel2_firmware"] is None
    assert any(address == 1003 for address, _count, _unit in modbus.reads)


async def test_single_panel_does_not_touch_panel_2_firmware() -> None:
    unit, modbus = client({954: 1})
    await unit.get_status()
    assert all(address != 1003 for address, _count, _unit in modbus.reads)
    firmware_reads = [read for read in modbus.reads if read[0] == 999]
    assert firmware_reads == [(999, 4, 1)]


def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "KOMFOVENT_HOST",
        "KOMFOVENT_PORT",
        "KOMFOVENT_UNIT_ID",
        "KOMFOVENT_TIMEOUT",
        "KOMFOVENT_MIN_GAP_S",
    ):
        monkeypatch.delenv(name, raising=False)
    config = Config.from_env()
    assert config.host == "192.168.0.60"
    assert config.port == 502
    assert config.unit_id == 1
    assert config.timeout == 5
    assert config.min_gap_s == 0.5
