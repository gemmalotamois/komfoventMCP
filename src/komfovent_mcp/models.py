"""Decode raw holding registers into the values the tools return."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from komfovent_mcp.errors import KomfoventError
from komfovent_mcp.registers import (
    ALARMS,
    FLOW_CONTROL,
    FLOW_MAX,
    FLOW_UNITS,
    HEAT_EXCHANGER,
    HEATING_BITS,
    HOLIDAY_MICROVENTILATION_MAX,
    HOLIDAY_MICROVENTILATION_MIN,
    HOLIDAY_YEAR_MAX,
    HOLIDAY_YEAR_MIN,
    MODE_SETTINGS,
    MODES,
    OVERRIDE_ACTIVATION,
    OVERRIDE_DELAY_START_MAX,
    OVERRIDE_DELAY_STOP_MAX,
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
    TIMER_MAX,
    TIMER_MIN,
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


def timer_minutes_value(minutes: int, *, minimum: int = TIMER_MIN) -> int:
    if isinstance(minutes, bool):
        raise KomfoventError("Timer minutes must be an integer")
    if isinstance(minutes, float) and minutes.is_integer():
        minutes = int(minutes)
    if not isinstance(minutes, int):
        raise KomfoventError("Timer minutes must be an integer")
    if minutes < minimum or minutes > TIMER_MAX:
        raise KomfoventError(f"Timer minutes must be between {minimum} and {TIMER_MAX}")
    return minutes


def bounded_int_value(value: int, *, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise KomfoventError(f"{label} must be an integer")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int):
        raise KomfoventError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise KomfoventError(f"{label} must be between {minimum} and {maximum}")
    return value


def microventilation_value(value: int) -> int:
    return bounded_int_value(
        value,
        label="Holiday microventilation",
        minimum=HOLIDAY_MICROVENTILATION_MIN,
        maximum=HOLIDAY_MICROVENTILATION_MAX,
    )


def override_delay_start_value(minutes: int) -> int:
    return bounded_int_value(
        minutes,
        label="Override delay_start_minutes",
        minimum=0,
        maximum=OVERRIDE_DELAY_START_MAX,
    )


def override_delay_stop_value(minutes: int) -> int:
    return bounded_int_value(
        minutes,
        label="Override delay_stop_minutes",
        minimum=0,
        maximum=OVERRIDE_DELAY_STOP_MAX,
    )


def override_activation_value(activation: str) -> int:
    if not isinstance(activation, str):
        raise KomfoventError(
            f"Override activation must be one of: {', '.join(OVERRIDE_ACTIVATION.values())}"
        )
    name = activation.strip().lower()
    for code, label in OVERRIDE_ACTIVATION.items():
        if label == name:
            return code
    raise KomfoventError(
        f"Override activation must be one of: {', '.join(OVERRIDE_ACTIVATION.values())}"
    )


def parse_holiday_date(value: str | date) -> date:
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = date.fromisoformat(value.strip())
        except ValueError as exc:
            raise KomfoventError("Holiday dates must be YYYY-MM-DD") from exc
    else:
        raise KomfoventError("Holiday dates must be YYYY-MM-DD")
    if parsed.year < HOLIDAY_YEAR_MIN or parsed.year > HOLIDAY_YEAR_MAX:
        raise KomfoventError(
            f"Holiday year must be between {HOLIDAY_YEAR_MIN} and {HOLIDAY_YEAR_MAX}"
        )
    return parsed


def holiday_date_epoch(value: date) -> int:
    return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp())


def holiday_month_day_word(value: date) -> int:
    return (value.month << 8) | value.day


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
        "modes": _build_modes(raw),
    }


def _build_modes(raw: dict[int, int]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, spec in MODE_SETTINGS.items():
        if name == "holiday":
            result[name] = {
                "setpoint_c": _temperature(raw, spec["setpoint"]),
                "heating": _flag(raw, spec["heating"]),
                "microventilation": _raw(raw, spec["microventilation"]),
                "from_date": _holiday_date(raw, spec["year_from"], spec["month_day_from"]),
                "until_date": _holiday_date(
                    raw, spec["year_until"], spec["month_day_until"]
                ),
            }
            continue
        entry: dict[str, Any] = {
            "supply_flow": _u32(raw, spec["supply"]),
            "extract_flow": _u32(raw, spec["extract"]),
            "setpoint_c": _temperature(raw, spec["setpoint"]),
            "heating": _flag(raw, spec["heating"]),
        }
        if "timer" in spec:
            entry["timer_minutes"] = _raw(raw, spec["timer"])
        if name == "override":
            entry["activation"] = _enum(OVERRIDE_ACTIVATION, _raw(raw, spec["activation"]))
            entry["delay_start_minutes"] = _raw(raw, spec["delay_start"])
            entry["delay_stop_minutes"] = _raw(raw, spec["delay_stop"])
        result[name] = entry
    return result


def _holiday_date(raw: dict[int, int], year_reg: int, month_day_reg: int) -> str | None:
    year = _raw(raw, year_reg)
    month_day = _raw(raw, month_day_reg)
    if year is None or month_day is None:
        return None
    month = (month_day >> 8) & 0xFF
    day = month_day & 0xFF
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


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
