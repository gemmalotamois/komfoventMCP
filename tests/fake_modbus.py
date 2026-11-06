"""In-memory Modbus TCP stand-in."""

from __future__ import annotations

from pymodbus.exceptions import ConnectionException


class FakeResult:
    def __init__(self, registers: list[int] | None = None, error: bool = False) -> None:
        self.registers = registers or []
        self._error = error

    def isError(self) -> bool:  # pymodbus spelling
        return self._error

    def __str__(self) -> str:
        return "illegal data address" if self._error else "ok"


class FakeModbus:
    def __init__(
        self,
        store: dict[int, int] | None = None,
        failures: int = 0,
        illegal: set[int] | None = None,
    ) -> None:
        self.store = dict(store or {})
        self.connected = False
        self.reads: list[tuple[int, int, int]] = []
        self.writes: list[tuple] = []
        self.connects = 0
        self.failures = failures
        self.illegal = illegal or set()

    async def connect(self) -> bool:
        self.connects += 1
        self.connected = True
        return True

    def close(self) -> None:
        self.connected = False

    async def read_holding_registers(
        self,
        address: int,
        *,
        count: int = 1,
        device_id: int = 1,
        no_response_expected: bool = False,
    ) -> FakeResult:
        if self.failures:
            self.failures -= 1
            raise ConnectionException("connection lost")
        self.reads.append((address, count, device_id))
        if address in self.illegal:
            return FakeResult(error=True)
        return FakeResult([self.store.get(address + 1 + index, 0) for index in range(count)])

    async def write_register(
        self,
        address: int,
        value: int,
        *,
        device_id: int = 1,
        no_response_expected: bool = False,
    ) -> FakeResult:
        self.writes.append(("one", address, value, device_id))
        self.store[address + 1] = value
        return FakeResult()

    async def write_registers(
        self,
        address: int,
        values: list[int],
        *,
        device_id: int = 1,
        no_response_expected: bool = False,
    ) -> FakeResult:
        self.writes.append(("many", address, list(values), device_id))
        for index, word in enumerate(values):
            self.store[address + 1 + index] = word
        return FakeResult()
