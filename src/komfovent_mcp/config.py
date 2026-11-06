"""Runtime configuration loaded from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Modbus TCP target for one Komfovent controller."""

    host: str = "192.168.0.60"
    port: int = 502
    unit_id: int = 1
    timeout: float = 5.0
    min_gap_s: float = 0.5

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            host=os.environ.get("KOMFOVENT_HOST", "192.168.0.60"),
            port=_int_env("KOMFOVENT_PORT", 502),
            unit_id=_int_env("KOMFOVENT_UNIT_ID", 1),
            timeout=_float_env("KOMFOVENT_TIMEOUT", 5.0),
            min_gap_s=_float_env("KOMFOVENT_MIN_GAP_S", 0.5),
        )


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)
