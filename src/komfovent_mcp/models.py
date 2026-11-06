"""Decode raw holding registers into the values the tools return."""

from __future__ import annotations

from typing import Any

from komfovent_mcp.errors import KomfoventError
from komfovent_mcp.registers import (
    ALARMS,
    FLOW_CONTROL,
    FLOW_MAX,
    FLOW_UNITS,
    HEAT_EXCHANGER,
    HEATING_BITS,
    MODES,
    REG_ALARMS,
    REG_AQ_TEMPERATURE,
    REG_AUTO,
    REG_ECO,
    REG_FIRMWARE,
    REG_FLOW_CONTROL,
    REG_FLOW_UNIT,
    REG_MODE,
    REG_NEXT_MODE,
    REG_NEXT_TIME,
    REG_NEXT_WEEKDAY,
    REG_PANEL1_FIRMWARE,
    REG_PANEL2_FIRMWARE,
    REG_POWER,
    REG_SCHEDULER,
    REG_STATUS,
    REG_TEMP_CONTROL,
    SCHEDULER_MODES,
    SETPOINT_BY_MODE,
    SPI_SCALE,
    STATUS_BITS,
    TEMPERATURE_CONTROL,
    TEMPERATURE_MAX,
    TEMPERATURE_MIN,
    WEEKDAYS,
)


def temperature_word(celsius: float) -> int:
    """Convert °C to the controller's tenth-degree register value."""
    if isinstance(celsius, bool) or not isinstance(celsius, (int, float)):
        raise KomfoventError("Temperature must be a number of degrees Celsius")
    word = int(round(float(celsius) * 10))
    if word < TEMPERATURE_MIN or word > TEMPERATURE_MAX:
        raise KomfoventError("Temperature must be between 5.0 and 40.0 °C")
    return word


def flow_value(flow: int) -> int:
    if isinstance(flow, bool):
        raise KomfoventError("Flow must be an integer")
    if isinstance(flow, float) and flow.is_integer():
        flow = int(flow)
    if not isinstance(flow, int):
        raise KomfoventError("Flow must be an integer")
    if flow < 0 or flow > FLOW_MAX:
        raise KomfoventError(f"Flow must be between 0 and {FLOW_MAX}")
    return flow


def describe_alarm(code: int) -> dict[str, Any]:
    known = ALARMS.get(code)
    if known is None:
        return {
            "code": code,
            "label": None,
            "message": f"Unknown alarm {code}",
            "severity": "unknown",
        }
    label, message = known
    return {
        "code": code,
        "label": label,
        "message": message,
        "severity": "warning" if label.startswith("W") else "fault",
    }


def decode_controller_firmware(value: int) -> tuple[str, str]:
    """Return (controller, version).

    C8 packs five fields, starting with a 4-bit major. C6 packs four fields and
    its major is an 8-bit value that is small on real firmware. A C6 decode of
    this unit's word is 17.5.50.77, which is the C8 value 1.1.5.50.77 with the
    leading nibble absorbed into the major.
    """
    c6_major = (value >> 24) & 0xFF
    if c6_major >= 16:
        parts = (
            (value >> 28) & 0xF,
            (value >> 24) & 0xF,
            (value >> 20) & 0xF,
            (value >> 12) & 0xFF,
            value & 0xFFF,
        )
        return "c8", ".".join(str(part) for part in parts)
    parts = (
        c6_major,
        (value >> 20) & 0xF,
        (value >> 12) & 0xFF,
        value & 0xFFF,
    )
    return "c6", ".".join(str(part) for part in parts)


def decode_panel_firmware(value: int) -> str | None:
    if value == 0:
        return None
    parts = (
        (value >> 24) & 0xFF,
        (value >> 20) & 0xF,
        (value >> 12) & 0xFF,
        value & 0xFFF,
    )
    return ".".join(str(part) for part in parts)


def build_status(raw: dict[int, int], *, host: str, unit_id: int) -> dict[str, Any]:
    mode_value = _raw(raw, REG_MODE)
    setpoint_register = SETPOINT_BY_MODE.get(mode_value) if mode_value is not None else None
    firmware_word = _u32(raw, REG_FIRMWARE)
    if firmware_word:
        controller, firmware = decode_controller_firmware(firmware_word)
    else:
        controller, firmware = None, None
    flow_code = _raw(raw, REG_FLOW_UNIT)
    return {
        "host": host,
        "unit_id": unit_id,
        "controller": controller,
        "firmware": firmware,
        "panel1_firmware": _panel(raw, REG_PANEL1_FIRMWARE),
        "panel2_firmware": _panel(raw, REG_PANEL2_FIRMWARE),
        "power": _flag(raw, REG_POWER),
        "mode": _enum(MODES, mode_value),
        "eco": _flag(raw, REG_ECO),
        "auto": _flag(raw, REG_AUTO),
        "setpoint_c": _temperature(raw, setpoint_register) if setpoint_register else None,
        "air_quality_setpoint_c": _temperature(raw, REG_AQ_TEMPERATURE),
        "temperature_control": _enum(TEMPERATURE_CONTROL, _raw(raw, REG_TEMP_CONTROL)),
        "flow_control": _enum(FLOW_CONTROL, _raw(raw, REG_FLOW_CONTROL)),
        "flow_unit": FLOW_UNITS.get(flow_code) if flow_code is not None else None,
        "temperatures_c": {
            "supply": _temperature(raw, 902),
            "extract": _temperature(raw, 903),
            "outdoor": _temperature(raw, 904),
            "water": _temperature(raw, 905),
            "exhaust": _temperature(raw, 961),
            "room": _temperature(raw, 946),
        },
        "humidity": {
            "panel1_percent": _percent(raw, 947),
            "panel2_percent": _percent(raw, 950),
            "indoor_g_m3": _absolute_humidity(raw, 956),
            "outdoor_g_m3": _absolute_humidity(raw, 957),
        },
        "air_quality": {
            "panel1": _air_quality(raw, 948),
            "panel2": _air_quality(raw, 951),
            "sensor1": _air_quality(raw, 952),
            "sensor2": _air_quality(raw, 953),
        },
        "flows": {
            "supply": _u32(raw, 906),
            "extract": _u32(raw, 908),
            "unit": FLOW_UNITS.get(flow_code) if flow_code is not None else None,
        },
        "fans_percent": {
            "supply": _tenths(raw, 910),
            "extract": _tenths(raw, 911),
        },
        "actuators_percent": {
            "heat_exchanger": _tenths(raw, 912),
            "electric_heater": _tenths(raw, 913),
            "water_heater": _tenths(raw, 914),
            "water_cooler": _tenths(raw, 915),
            "dx": _signed_tenths(raw, 916),
            "dampers": _raw(raw, 918),
        },
        "filter_impurity_percent": _raw(raw, 917),
        "pressures_pa": {
            "supply": _raw(raw, 919),
            "extract": _raw(raw, 920),
        },
        "power_w": _raw(raw, 921),
        "status": _bits(raw, REG_STATUS, STATUS_BITS),
        "heating": _bits(raw, 901, HEATING_BITS),
        "heat_exchanger": _enum(HEAT_EXCHANGER, _raw(raw, 955)),
        "panels": _panels(_raw(raw, 954)),
        "schedule": {
            "program": _enum(SCHEDULER_MODES, _raw(raw, REG_SCHEDULER)),
            "next_mode": _enum(MODES, _raw(raw, REG_NEXT_MODE)),
            "next_start": _clock(_raw(raw, REG_NEXT_TIME)),
            "next_weekday": _enum(WEEKDAYS, _raw(raw, REG_NEXT_WEEKDAY)),
        },
    }


def build_alarms(raw: dict[int, int]) -> dict[str, Any]:
    alarms = []
    for register in range(REG_ALARMS + 1, REG_ALARMS + 11):
        code = raw.get(register, 0)
        if code:
            alarms.append(describe_alarm(code))
    return {"count": raw.get(REG_ALARMS, 0), "alarms": alarms}


def build_energy(raw: dict[int, int]) -> dict[str, Any]:
    return {
        "power_w": _raw(raw, 921),
        "heater_power_w": _raw(raw, 922),
        "heat_recovery_w": _raw(raw, 923),
        "heat_exchanger_efficiency_percent": _raw(raw, 924),
        "energy_saving_percent": _raw(raw, 925),
        "specific_power_w_per_m3h": _spi(raw, 926),
        "specific_power_day_w_per_m3h": _spi(raw, 945),
        "ahu_wh": {"day": _u32(raw, 927), "month": _u32(raw, 929), "total": _u32(raw, 931)},
        "heater_wh": {"day": _u32(raw, 933), "month": _u32(raw, 935), "total": _u32(raw, 937)},
        "recovered_wh": {
            "day": _u32(raw, 939),
            "month": _u32(raw, 941),
            "total": _u32(raw, 943),
        },
    }


def _raw(raw: dict[int, int], register: int) -> int | None:
    if register not in raw:
        return None
    return raw[register]


def _u32(raw: dict[int, int], register: int) -> int | None:
    high = _raw(raw, register)
    low = _raw(raw, register + 1)
    if high is None or low is None:
        return None
    return (high << 16) + low


def _i16(raw: dict[int, int], register: int) -> int | None:
    value = _raw(raw, register)
    if value is None:
        return None
    return value - ((value >> 15) << 16)


def _temperature(raw: dict[int, int], register: int | None) -> float | None:
    if register is None:
        return None
    value = _i16(raw, register)
    if value is None or value < -500 or value > 1200:
        return None
    return round(value / 10, 1)


def _tenths(raw: dict[int, int], register: int) -> float | None:
    value = _raw(raw, register)
    if value is None:
        return None
    return round(value / 10, 1)


def _signed_tenths(raw: dict[int, int], register: int) -> float | None:
    value = _i16(raw, register)
    if value is None:
        return None
    return round(value / 10, 1)


def _percent(raw: dict[int, int], register: int) -> int | None:
    value = _i16(raw, register)
    if value is None or value < 0 or value > 100:
        return None
    return value


def _absolute_humidity(raw: dict[int, int], register: int) -> float | None:
    value = _raw(raw, register)
    if value is None or value in (0, 65534, 65535):
        return None
    return round(value / 100, 2)


def _air_quality(raw: dict[int, int], register: int) -> int | None:
    value = _raw(raw, register)
    if value is None or value in (32768, 65535):
        return None
    return value


def _spi(raw: dict[int, int], register: int) -> float | None:
    value = _raw(raw, register)
    if value is None:
        return None
    return round(value / SPI_SCALE, 3)


def _flag(raw: dict[int, int], register: int) -> bool | None:
    value = _raw(raw, register)
    if value is None:
        return None
    return bool(value)


def _enum(mapping: dict[int, str], value: int | None) -> str | None:
    if value is None:
        return None
    return mapping.get(value, f"unknown_{value}")


def _bits(raw: dict[int, int], register: int, names: tuple[str, ...]) -> list[str]:
    value = _raw(raw, register)
    if not value:
        return []
    return [name for bit, name in enumerate(names) if value & (1 << bit)]


def _panels(mask: int | None) -> list[str]:
    if not mask:
        return []
    names = []
    if mask & 1:
        names.append("panel1")
    if mask & 2:
        names.append("panel2")
    return names


def _panel(raw: dict[int, int], register: int) -> str | None:
    word = _u32(raw, register)
    if not word:
        return None
    return decode_panel_firmware(word)


def _clock(minutes: int | None) -> str | None:
    if minutes is None or minutes > 1439:
        return None
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
