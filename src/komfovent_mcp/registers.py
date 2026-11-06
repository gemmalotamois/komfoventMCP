"""Modbus addresses and enumerations for Komfovent C6/C8 controllers.

Register numbers are the 1-based values from the Komfovent manuals.
The Modbus PDU address is that number minus one.
"""

from __future__ import annotations

REG_POWER = 1
REG_ECO = 3
REG_AUTO = 4
REG_MODE = 5
REG_SCHEDULER = 6
REG_NEXT_MODE = 7
REG_NEXT_TIME = 8
REG_NEXT_WEEKDAY = 9
REG_TEMP_CONTROL = 11
REG_FLOW_CONTROL = 12
REG_FLOW_UNIT = 28

REG_AQ_TEMPERATURE = 206
REG_ALARMS = 600
REG_STATUS = 900
REG_SENSORS = 900
REG_SENSOR_COUNT = 62  # 900..961
REG_FIRMWARE = 1000
REG_PANEL1_FIRMWARE = 1002
REG_PANEL2_FIRMWARE = 1004
REG_FILTER_RESET = 1051

REG_TIME = 29
REG_YEAR = 30
REG_MONTH_DAY = 31
REG_EPOCH_TIME = 33
REG_MODE_SETTINGS_START = 100
REG_MODE_SETTINGS_COUNT = 59  # 100..158

ALARM_RESET_VALUE = 0x99C6
TEMPERATURE_MIN = 50  # 5.0 °C, stored as tenths
TEMPERATURE_MAX = 400  # 40.0 °C
FLOW_MAX = 200_000
TIMER_MIN = 0
TIMER_MAX = 300
OVERRIDE_DELAY_START_MAX = 10
OVERRIDE_DELAY_STOP_MAX = 30
HOLIDAY_MICROVENTILATION_MIN = 1
HOLIDAY_MICROVENTILATION_MAX = 4
HOLIDAY_YEAR_MIN = 2017
HOLIDAY_YEAR_MAX = 2035
DEFAULT_TIMED_MODE_MINUTES = 60
DEFAULT_HOLIDAY_DAYS = 1

# This C8 stores specific power as thousandths of W/(m³/h): 572 -> 0.572.
SPI_SCALE = 1000

MODES: dict[int, str] = {
    0: "standby",
    1: "away",
    2: "normal",
    3: "intensive",
    4: "boost",
    5: "kitchen",
    6: "fireplace",
    7: "override",
    8: "holiday",
    9: "air_quality",
    10: "off",
}

DIRECT_WRITABLE_MODES = ("away", "normal", "intensive", "boost")
TIMED_MODES: dict[str, int] = {
    "kitchen": 130,
    "fireplace": 137,
    "override": 145,
}
WRITABLE_MODES = (
    *DIRECT_WRITABLE_MODES,
    "kitchen",
    "fireplace",
    "override",
    "holiday",
)

OVERRIDE_ACTIVATION: dict[int, str] = {
    0: "all_time",
    1: "if_on",
    2: "if_off",
}

SCHEDULER_MODES = {
    0: "stay_at_home",
    1: "working_week",
    2: "office",
    3: "custom",
}

TEMPERATURE_CONTROL = {0: "supply", 1: "extract", 2: "balance", 3: "room"}
FLOW_CONTROL = {0: "cav", 1: "vav", 2: "dcv", 3: "off"}
FLOW_UNITS = {0: "m3/h", 1: "l/s"}
HEAT_EXCHANGER = {0: "plate", 1: "rotary"}
WEEKDAYS = {
    0: "none",
    1: "monday",
    2: "tuesday",
    3: "wednesday",
    4: "thursday",
    5: "friday",
    6: "saturday",
    7: "sunday",
}

STATUS_BITS = (
    "starting",
    "stopping",
    "fan",
    "rotor",
    "heating",
    "cooling",
    "heating_denied",
    "cooling_denied",
    "flow_down",
    "free_heating",
    "free_cooling",
    "fault_alarm",
    "warning_alarm",
)

HEATING_BITS = ("electric_heater", "water_coil", "dx_unit")

# Active-mode temperature setpoint. Register 5 only accepts the first four as writes.
SETPOINT_BY_MODE = {
    1: 104,
    2: 110,
    3: 116,
    4: 122,
    5: 128,
    6: 135,
    7: 142,
    8: 147,
    9: REG_AQ_TEMPERATURE,
}

# supply/extract are 32-bit flow setpoints. Holiday has temperature, heater,
# micro-ventilation frequency, and date range.
MODE_SETTINGS: dict[str, dict[str, int]] = {
    "away": {"supply": 100, "extract": 102, "setpoint": 104, "heating": 105},
    "normal": {"supply": 106, "extract": 108, "setpoint": 110, "heating": 111},
    "intensive": {"supply": 112, "extract": 114, "setpoint": 116, "heating": 117},
    "boost": {"supply": 118, "extract": 120, "setpoint": 122, "heating": 123},
    "kitchen": {
        "supply": 124,
        "extract": 126,
        "setpoint": 128,
        "heating": 129,
        "timer": 130,
    },
    "fireplace": {
        "supply": 131,
        "extract": 133,
        "setpoint": 135,
        "heating": 136,
        "timer": 137,
    },
    "override": {
        "supply": 138,
        "extract": 140,
        "setpoint": 142,
        "heating": 143,
        "activation": 144,
        "timer": 145,
        "delay_start": 157,
        "delay_stop": 158,
    },
    "holiday": {
        "microventilation": 146,
        "setpoint": 147,
        "heating": 148,
        "from_epoch": 149,
        "until_epoch": 151,
        "year_from": 153,
        "month_day_from": 154,
        "year_until": 155,
        "month_day_until": 156,
    },
}

WRITABLE = frozenset(
    {
        REG_POWER,
        REG_ECO,
        REG_AUTO,
        REG_MODE,
        REG_AQ_TEMPERATURE,
        REG_ALARMS,
        REG_FILTER_RESET,
        *(
            register
            for spec in MODE_SETTINGS.values()
            for register in spec.values()
        ),
    }
)

# code -> (panel label, message). Sourced from the C6/C8 Modbus manuals.
ALARMS: dict[int, tuple[str, str]] = {
    1: ("F1", "Supply flow not reached"),
    2: ("F2", "Exhaust flow not reached"),
    3: ("F3", "Water temperature B5 too low"),
    4: ("F4", "Low supply air temperature"),
    5: ("F5", "High supply air temperature"),
    6: ("F6", "Electric heater overheat"),
    7: ("F7", "Heat exchanger failure"),
    8: ("F8", "Heat exchanger icing"),
    9: ("F9", "Internal fire"),
    10: ("F10", "External fire"),
    11: ("F11", "Supply air temperature B1 short"),
    12: ("F12", "Supply air temperature B1 not connected"),
    13: ("F13", "Extract air temperature B2 short"),
    14: ("F14", "Extract air temperature B2 not connected"),
    15: ("F15", "Outdoor air temperature B3 short"),
    16: ("F16", "Outdoor air temperature B3 not connected"),
    17: ("F17", "Exhaust air temperature B4 short"),
    18: ("F18", "Exhaust air temperature B4 not connected"),
    19: ("F19", "Water temperature B5 short"),
    20: ("F20", "Water temperature B5 not connected"),
    21: ("F21", "Supply temperature after heat exchanger B10 short"),
    22: ("F22", "Supply temperature after heat exchanger B10 not connected"),
    23: ("F23", "Flash fail"),
    24: ("F24", "24V supply voltage too low"),
    25: ("F25", "24V supply voltage too high"),
    26: ("F26", "24V supply voltage overloaded"),
    28: ("F28", "Room temperature sensor fail"),
    29: ("F29", "Room humidity sensor fail"),
    30: ("F30", "Humidity sensor failure"),
    31: ("F31", "Impurity sensor failure"),
    32: ("F32", "Heat exchanger failure"),
    33: ("F33", "Heat exchanger failure"),
    34: ("F34", "Heat exchanger failure"),
    35: ("F35", "Heat exchanger failure"),
    36: ("F36", "Heat exchanger failure"),
    37: ("F37", "Heat exchanger failure"),
    38: ("F38", "Air flow sensor failure"),
    39: ("F39", "Air flow sensor failure"),
    40: ("F40", "Communication error"),
    41: ("F41", "Fire dampers failure"),
    42: ("F42", "Fire damper failure"),
    43: ("F43", "Fire damper failure"),
    44: ("F44", "Fire damper failure"),
    45: ("F45", "Fire damper failure"),
    46: ("F46", "External fire alarm"),
    47: ("F47", "External fire alarm"),
    48: ("F48", "External fire alarm"),
    49: ("F49", "External fire alarm"),
    50: ("F50", "External fire alarm"),
    51: ("F51", "Electric heater failure"),
    52: ("F52", "Electric preheater failure"),
    129: ("W1", "Change air filter"),
    130: ("W2", "Service mode"),
    131: ("W3", "Water temperature B5 too low"),
    132: ("W4", "Humidity sensor failure"),
    133: ("W5", "Impurity sensor failure"),
    134: ("W6", "Low heat exchanger efficiency"),
}
