"""Async Modbus TCP client for one Komfovent controller."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from typing import Any, TypeVar

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

from komfovent_mcp.config import Config
from komfovent_mcp.errors import KomfoventError
from komfovent_mcp.models import (
    build_alarms,
    build_energy,
    build_status,
    flow_value,
    holiday_date_epoch,
    holiday_month_day_word,
    microventilation_value,
    override_activation_value,
    override_delay_start_value,
    override_delay_stop_value,
    parse_holiday_date,
    temperature_word,
    timer_minutes_value,
)
from komfovent_mcp.registers import (
    ALARM_RESET_VALUE,
    DEFAULT_HOLIDAY_DAYS,
    DEFAULT_TIMED_MODE_MINUTES,
    DIRECT_WRITABLE_MODES,
    MODE_SETTINGS,
    MODES,
    REG_ALARMS,
    REG_AQ_TEMPERATURE,
    REG_AUTO,
    REG_ECO,
    REG_FILTER_RESET,
    REG_FIRMWARE,
    REG_MODE,
    REG_MODE_SETTINGS_COUNT,
    REG_MODE_SETTINGS_START,
    REG_MONTH_DAY,
    REG_PANEL2_FIRMWARE,
    REG_POWER,
    REG_SENSOR_COUNT,
    REG_SENSORS,
    REG_YEAR,
    SETPOINT_BY_MODE,
    TIMED_MODES,
    WRITABLE,
    WRITABLE_MODES,
)

T = TypeVar("T")
_RETRYABLE = (ConnectionException, ModbusIOException, OSError, asyncio.TimeoutError)


class KomfoventClient:
    """One persistent Modbus TCP session.

    Transactions are serialized and separated by at least ``min_gap_s``
    (500 ms by default), which is the minimum the controller manual allows.
    """

    def __init__(self, config: Config, modbus: Any = None) -> None:
        self.config = config
        self._modbus: Any = modbus
        self._lock = asyncio.Lock()
        self._last: float | None = None

    async def close(self) -> None:
        if self._modbus is not None:
            self._modbus.close()

    async def get_status(self) -> dict[str, Any]:
        async with self._lock:
            return await self._status()

    async def get_alarms(self) -> dict[str, Any]:
        async with self._lock:
            raw = await self._read(REG_ALARMS, 11)
            return build_alarms(raw)

    async def get_energy(self) -> dict[str, Any]:
        async with self._lock:
            raw = await self._read(921, 25)
            return build_energy(raw)

    async def set_power(self, on: bool) -> dict[str, Any]:
        async with self._lock:
            await self._write_u16(REG_POWER, 1 if on else 0)
            return await self._status()

    async def set_mode(
        self,
        mode: str,
        *,
        minutes: int | None = None,
        from_date: str | date | None = None,
        until_date: str | date | None = None,
    ) -> dict[str, Any]:
        name = _mode_name(mode, WRITABLE_MODES)
        if name in DIRECT_WRITABLE_MODES:
            if minutes is not None or from_date is not None or until_date is not None:
                raise KomfoventError(
                    f"{name} mode does not accept minutes, from_date, or until_date"
                )
            async with self._lock:
                await self._write_u16(REG_MODE, _mode_value(name))
                return await self._status()
        if name in TIMED_MODES:
            if from_date is not None or until_date is not None:
                raise KomfoventError(
                    f"{name} mode uses minutes, not from_date or until_date"
                )
            timer_reg = TIMED_MODES[name]
            validated_minutes = (
                timer_minutes_value(minutes, minimum=1) if minutes is not None else None
            )
            async with self._lock:
                if validated_minutes is None:
                    current = (await self._read(timer_reg, 1)).get(timer_reg, 0)
                    validated_minutes = (
                        current if current and current > 0 else DEFAULT_TIMED_MODE_MINUTES
                    )
                await self._write_u16(timer_reg, validated_minutes)
                return await self._status()
        if minutes is not None:
            raise KomfoventError("holiday mode uses from_date and until_date, not minutes")
        start = parse_holiday_date(from_date) if from_date is not None else None
        end = parse_holiday_date(until_date) if until_date is not None else None
        async with self._lock:
            if start is None:
                start = await self._controller_date()
            if end is None:
                end = start + timedelta(days=DEFAULT_HOLIDAY_DAYS)
            if end < start:
                raise KomfoventError("Holiday until_date must not be earlier than from_date")
            await self._write_holiday_dates(start, end)
            return await self._status()

    async def set_temperature(self, celsius: float) -> dict[str, Any]:
        """Write the active mode setpoint and the air-quality setpoint."""
        word = temperature_word(celsius)
        async with self._lock:
            mode = (await self._read(REG_MODE, 1)).get(REG_MODE, 0)
            setpoint = SETPOINT_BY_MODE.get(mode)
            if setpoint is not None:
                await self._write_i16(setpoint, word)
            if setpoint != REG_AQ_TEMPERATURE:
                await self._write_i16(REG_AQ_TEMPERATURE, word)
            return await self._status()

    async def set_eco(self, on: bool) -> dict[str, Any]:
        async with self._lock:
            await self._write_u16(REG_ECO, 1 if on else 0)
            return await self._status()

    async def set_auto(self, on: bool) -> dict[str, Any]:
        async with self._lock:
            await self._write_u16(REG_AUTO, 1 if on else 0)
            return await self._status()

    async def set_mode_settings(
        self,
        mode: str,
        supply_flow: int | None = None,
        extract_flow: int | None = None,
        setpoint_c: float | None = None,
        heating: bool | None = None,
        timer_minutes: int | None = None,
        activation: str | None = None,
        delay_start_minutes: int | None = None,
        delay_stop_minutes: int | None = None,
        microventilation: int | None = None,
        from_date: str | date | None = None,
        until_date: str | date | None = None,
    ) -> dict[str, Any]:
        name = _mode_name(mode, tuple(MODE_SETTINGS))
        spec = MODE_SETTINGS[name]
        if all(
            value is None
            for value in (
                supply_flow,
                extract_flow,
                setpoint_c,
                heating,
                timer_minutes,
                activation,
                delay_start_minutes,
                delay_stop_minutes,
                microventilation,
                from_date,
                until_date,
            )
        ):
            raise KomfoventError(
                "Provide at least one mode setting to change"
            )
        if (supply_flow is not None or extract_flow is not None) and "supply" not in spec:
            raise KomfoventError(f"{name} mode has no supply or extract flow setting")
        if timer_minutes is not None and "timer" not in spec:
            raise KomfoventError(f"{name} mode has no timer setting")
        if (
            activation is not None
            or delay_start_minutes is not None
            or delay_stop_minutes is not None
        ) and name != "override":
            raise KomfoventError(
                "activation, delay_start_minutes, and delay_stop_minutes only apply to override mode"
            )
        if (
            microventilation is not None
            or from_date is not None
            or until_date is not None
        ) and name != "holiday":
            raise KomfoventError(
                "microventilation, from_date, and until_date only apply to holiday mode"
            )
        supply = flow_value(supply_flow) if supply_flow is not None else None
        extract = flow_value(extract_flow) if extract_flow is not None else None
        setpoint = temperature_word(setpoint_c) if setpoint_c is not None else None
        timer = timer_minutes_value(timer_minutes) if timer_minutes is not None else None
        act_code = (
            override_activation_value(activation) if activation is not None else None
        )
        delay_start = (
            override_delay_start_value(delay_start_minutes)
            if delay_start_minutes is not None
            else None
        )
        delay_stop = (
            override_delay_stop_value(delay_stop_minutes)
            if delay_stop_minutes is not None
            else None
        )
        micro = (
            microventilation_value(microventilation)
            if microventilation is not None
            else None
        )
        start = parse_holiday_date(from_date) if from_date is not None else None
        end = parse_holiday_date(until_date) if until_date is not None else None
        if start is not None and end is not None and end < start:
            raise KomfoventError("Holiday until_date must not be earlier than from_date")
        async with self._lock:
            if supply is not None:
                await self._write_u32(spec["supply"], supply)
            if extract is not None:
                await self._write_u32(spec["extract"], extract)
            if setpoint is not None:
                await self._write_i16(spec["setpoint"], setpoint)
            if heating is not None:
                await self._write_u16(spec["heating"], 1 if heating else 0)
            if timer is not None:
                await self._write_u16(spec["timer"], timer)
            if act_code is not None:
                await self._write_u16(spec["activation"], act_code)
            if delay_start is not None:
                await self._write_u16(spec["delay_start"], delay_start)
            if delay_stop is not None:
                await self._write_u16(spec["delay_stop"], delay_stop)
            if micro is not None:
                await self._write_u16(spec["microventilation"], micro)
            if start is not None or end is not None:
                await self._write_holiday_dates(start, end)
            return await self._status()

    async def reset_alarms(self) -> dict[str, Any]:
        """Clear active alarms. The controller restores the previous mode."""
        async with self._lock:
            await self._write_u16(REG_ALARMS, ALARM_RESET_VALUE)
            return build_alarms(await self._read(REG_ALARMS, 11))

    async def reset_filters(self) -> dict[str, Any]:
        """Reset the filter clogging counter. The unit applies this above 1%."""
        async with self._lock:
            await self._write_u16(REG_FILTER_RESET, 1)
            return await self._status()

    async def _status(self) -> dict[str, Any]:
        raw: dict[int, int] = {}
        raw.update(await self._read(1, 44))
        raw.update(await self._read(REG_MODE_SETTINGS_START, REG_MODE_SETTINGS_COUNT))
        raw.update(await self._read(REG_AQ_TEMPERATURE, 1))
        raw.update(await self._read(REG_SENSORS, REG_SENSOR_COUNT))
        raw.update(await self._read(REG_FIRMWARE, 4))
        if (raw.get(954) or 0) & 0b10:
            try:
                raw.update(await self._read(REG_PANEL2_FIRMWARE, 2))
            except KomfoventError:
                # A missing second panel answers illegal-data on 1004-1005.
                pass
        return build_status(raw, host=self.config.host, unit_id=self.config.unit_id)

    async def _controller_date(self) -> date:
        raw = await self._read(REG_YEAR, 2)
        year = raw.get(REG_YEAR, 0)
        month_day = raw.get(REG_MONTH_DAY, 0)
        month = (month_day >> 8) & 0xFF
        day = month_day & 0xFF
        try:
            return date(year, month, day)
        except ValueError:
            return date.today()

    async def _write_holiday_dates(
        self,
        start: date | None,
        end: date | None,
    ) -> None:
        spec = MODE_SETTINGS["holiday"]
        if start is not None:
            await self._write_u32(spec["from_epoch"], holiday_date_epoch(start))
            await self._write_u16(spec["year_from"], start.year)
            await self._write_u16(spec["month_day_from"], holiday_month_day_word(start))
        if end is not None:
            await self._write_u32(spec["until_epoch"], holiday_date_epoch(end))
            await self._write_u16(spec["year_until"], end.year)
            await self._write_u16(spec["month_day_until"], holiday_month_day_word(end))

    async def _read(self, register: int, count: int) -> dict[int, int]:
        result = await self._request(
            lambda: self._modbus.read_holding_registers(
                register - 1,
                count=count,
                device_id=self.config.unit_id,
            )
        )
        return dict(enumerate(result.registers, start=register))

    async def _write_u16(self, register: int, value: int) -> None:
        self._check_writable(register)
        if not 0 <= value <= 0xFFFF:
            raise KomfoventError(f"Value {value} does not fit in one register")
        await self._request(
            lambda: self._modbus.write_register(
                register - 1,
                value,
                device_id=self.config.unit_id,
            )
        )

    async def _write_i16(self, register: int, value: int) -> None:
        self._check_writable(register)
        if not -32768 <= value <= 32767:
            raise KomfoventError(f"Value {value} does not fit in a signed register")
        unsigned = value & 0xFFFF
        await self._request(
            lambda: self._modbus.write_register(
                register - 1,
                unsigned,
                device_id=self.config.unit_id,
            )
        )

    async def _write_u32(self, register: int, value: int) -> None:
        self._check_writable(register)
        if not 0 <= value <= 0xFFFFFFFF:
            raise KomfoventError(f"Value {value} does not fit in two registers")
        words = [(value >> 16) & 0xFFFF, value & 0xFFFF]
        await self._request(
            lambda: self._modbus.write_registers(
                register - 1,
                words,
                device_id=self.config.unit_id,
            )
        )

    async def _request(self, operation: Callable[[], Awaitable[T]]) -> T:
        await self._pace()
        try:
            await self._ensure()
            result = await operation()
        except _RETRYABLE:
            self._mark_down()
            self._last = time.monotonic()
            await self._pace()
            try:
                await self._ensure()
                result = await operation()
            except Exception as exc:
                self._last = time.monotonic()
                raise KomfoventError(
                    f"Modbus request to {self.config.host}:{self.config.port} failed: {exc}"
                ) from exc
        self._last = time.monotonic()
        if getattr(result, "isError", lambda: False)():
            raise KomfoventError(f"Modbus error from {self.config.host}: {result}")
        return result

    async def _ensure(self) -> None:
        if self._modbus is None:
            self._modbus = AsyncModbusTcpClient(
                self.config.host,
                port=self.config.port,
                timeout=self.config.timeout,
                retries=0,
            )
        if getattr(self._modbus, "connected", False):
            return
        ok = await self._modbus.connect()
        if not ok:
            raise KomfoventError(
                f"Could not connect to Komfovent at {self.config.host}:{self.config.port}"
            )

    async def _pace(self) -> None:
        if self._last is None:
            return
        remaining = self.config.min_gap_s - (time.monotonic() - self._last)
        if remaining > 0:
            await asyncio.sleep(remaining)

    def _mark_down(self) -> None:
        if self._modbus is None:
            return
        try:
            self._modbus.close()
        except Exception:
            pass

    @staticmethod
    def _check_writable(register: int) -> None:
        if register not in WRITABLE:
            raise KomfoventError(f"Register {register} is not writable")


def _mode_name(mode: str, allowed: tuple[str, ...]) -> str:
    if not isinstance(mode, str):
        raise KomfoventError(f"Mode must be one of: {', '.join(allowed)}")
    name = mode.strip().lower()
    if name not in allowed:
        raise KomfoventError(f"Mode must be one of: {', '.join(allowed)}")
    return name


def _mode_value(name: str) -> int:
    for value, label in MODES.items():
        if label == name:
            return value
    raise KomfoventError(f"Unknown mode {name}")
