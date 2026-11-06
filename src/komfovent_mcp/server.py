"""MCP server exposing a Komfovent air handling unit."""

from __future__ import annotations

import logging
import sys
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from komfovent_mcp.client import KomfoventClient
from komfovent_mcp.config import Config

logger = logging.getLogger("komfovent_mcp")

OperationMode = Literal[
    "away",
    "normal",
    "intensive",
    "boost",
    "kitchen",
    "fireplace",
    "override",
    "holiday",
]
SettingsMode = Literal[
    "away",
    "normal",
    "intensive",
    "boost",
    "kitchen",
    "fireplace",
    "override",
    "holiday",
]
OverrideActivationMode = Literal["all_time", "if_on", "if_off"]

_READ = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
_WRITE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
_RESET = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=True,
    open_world_hint=True,
)

_INSTRUCTIONS = (
    "Control one Komfovent air handling unit over Modbus TCP. "
    "get_status, get_alarms, and get_energy only read the unit. "
    "set_power, set_mode, set_temperature, set_eco, set_auto, and "
    "set_mode_settings change the live unit and return the new status. "
    "reset_alarms clears alarms and restores the previous operation mode. "
    "reset_filters recalibrates the filter clogging counter. "
    "Use the named tools; do not invent Modbus register numbers."
)


def build_server(client: KomfoventClient) -> MCPServer:
    server = MCPServer(
        "komfovent",
        instructions=_INSTRUCTIONS,
    )

    @server.tool(annotations=_READ)
    async def get_status() -> dict[str, Any]:
        """Read power, mode, setpoints, temperatures, flows, fans, filter, and firmware."""
        return await client.get_status()

    @server.tool(annotations=_WRITE)
    async def set_power(on: bool) -> dict[str, Any]:
        """Turn the air handling unit on or off."""
        return await client.set_power(on)

    @server.tool(annotations=_WRITE)
    async def set_mode(
        mode: OperationMode,
        minutes: int | None = None,
        from_date: str | None = None,
        until_date: str | None = None,
    ) -> dict[str, Any]:
        """Select away, normal, intensive, boost, kitchen, fireplace, override, or holiday.

        Timed modes (kitchen, fireplace, override) take optional minutes (1-300; defaults
        to the mode's stored timer or 60). Holiday mode takes optional from_date and
        until_date as YYYY-MM-DD (defaults to today through tomorrow on the controller clock).
        """
        return await client.set_mode(
            mode,
            minutes=minutes,
            from_date=from_date,
            until_date=until_date,
        )

    @server.tool(annotations=_WRITE)
    async def set_temperature(celsius: float) -> dict[str, Any]:
        """Set the active mode temperature and the air-quality temperature, in °C (5.0-40.0)."""
        return await client.set_temperature(celsius)

    @server.tool(annotations=_WRITE)
    async def set_eco(on: bool) -> dict[str, Any]:
        """Enable or disable ECO mode."""
        return await client.set_eco(on)

    @server.tool(annotations=_WRITE)
    async def set_auto(on: bool) -> dict[str, Any]:
        """Enable or disable AUTO mode."""
        return await client.set_auto(on)

    @server.tool(annotations=_READ)
    async def get_alarms() -> dict[str, Any]:
        """Read the active alarm count and decode alarm codes to fault or warning text."""
        return await client.get_alarms()

    @server.tool(annotations=_RESET)
    async def reset_alarms() -> dict[str, Any]:
        """Clear active alarms. The controller also restores the previous operation mode."""
        return await client.reset_alarms()

    @server.tool(annotations=_READ)
    async def get_energy() -> dict[str, Any]:
        """Read power, heat recovery, efficiency, and day/month/total energy in Wh."""
        return await client.get_energy()

    @server.tool(annotations=_WRITE)
    async def set_mode_settings(
        mode: SettingsMode,
        supply_flow: int | None = None,
        extract_flow: int | None = None,
        setpoint_c: float | None = None,
        heating: bool | None = None,
        timer_minutes: int | None = None,
        activation: OverrideActivationMode | None = None,
        delay_start_minutes: int | None = None,
        delay_stop_minutes: int | None = None,
        microventilation: int | None = None,
        from_date: str | None = None,
        until_date: str | None = None,
    ) -> dict[str, Any]:
        """Change settings for one mode (away, normal, intensive, boost, kitchen, fireplace, override, or holiday).

        Flows are in the unit's configured unit (m3/h or l/s). Temperature is °C (5.0-40.0).
        timer_minutes (0-300) applies to kitchen, fireplace, and override.
        activation ('all_time', 'if_on', 'if_off'), delay_start_minutes (0-10), and
        delay_stop_minutes (0-30) apply to override.
        microventilation (1-4 times/day), from_date (YYYY-MM-DD), and until_date (YYYY-MM-DD)
        apply to holiday (which has no flow settings).
        Omit any argument you do not want to change.
        """
        return await client.set_mode_settings(
            mode,
            supply_flow=supply_flow,
            extract_flow=extract_flow,
            setpoint_c=setpoint_c,
            heating=heating,
            timer_minutes=timer_minutes,
            activation=activation,
            delay_start_minutes=delay_start_minutes,
            delay_stop_minutes=delay_stop_minutes,
            microventilation=microventilation,
            from_date=from_date,
            until_date=until_date,
        )

    @server.tool(annotations=_RESET)
    async def reset_filters() -> dict[str, Any]:
        """Reset the filter clogging counter. The unit accepts this when clogging is above 1%."""
        return await client.reset_filters()

    @server.resource("komfovent://status", mime_type="application/json")
    async def status_resource() -> dict[str, Any]:
        """Current ventilation status."""
        return await client.get_status()

    @server.resource("komfovent://alarms", mime_type="application/json")
    async def alarms_resource() -> dict[str, Any]:
        """Active alarms."""
        return await client.get_alarms()

    @server.resource("komfovent://energy", mime_type="application/json")
    async def energy_resource() -> dict[str, Any]:
        """Power and energy counters."""
        return await client.get_energy()

    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    config = Config.from_env()
    logger.info("Komfovent MCP target %s:%s unit %s", config.host, config.port, config.unit_id)
    server = build_server(KomfoventClient(config))
    server.run(transport="stdio")
