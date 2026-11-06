# Komfovent MCP

MCP server for a Komfovent air handling unit over Modbus TCP. It talks to the controller with holding-register reads and writes (function codes 03, 06, and 16) and exposes named tools, so a client does not need the register map.

Set `KOMFOVENT_HOST` to the unit on your network. The published default, `192.168.0.60`, is the address Komfovent ships. The register map was checked against a C8 (firmware `1.1.5.50.77`) and matches C6/C6M; firmware register 1000 selects the version decoding.

Register numbers in the Komfovent manuals are 1-based. This server subtracts one before calling pymodbus. Requests are serialized and kept at least 500 ms apart.

## Tools

| Tool | Effect |
| --- | --- |
| `get_status` | Power, mode, setpoints, per-mode configuration (`modes`), temperatures, flows, fans, filter, alarms bits, firmware |
| `set_power` | On or off |
| `set_mode` | `away`, `normal`, `intensive`, `boost`, `kitchen`, `fireplace`, `override` (optional `minutes`), or `holiday` (optional `from_date` / `until_date`) |
| `set_temperature` | Active mode setpoint and air-quality setpoint, 5.0–40.0 °C |
| `set_eco` / `set_auto` | ECO and AUTO |
| `get_alarms` / `reset_alarms` | Active faults and warnings. Reset also restores the previous mode |
| `get_energy` | Power, recovery, and day/month/total energy in Wh |
| `set_mode_settings` | Flow, setpoint, heater, timer (`kitchen`/`fireplace`/`override`), activation/delays (`override`), or microventilation/dates (`holiday`) |
| `reset_filters` | Filter clogging calibration |

Resources `komfovent://status`, `komfovent://alarms`, and `komfovent://energy` return the same snapshots.

Writes change the live unit. Network settings and the settings-reset register (1050) are not exposed. Panel 2 firmware (registers 1004–1005) is read only when a second panel is connected; this C8 returns an illegal-data error for that pair.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Run the server on stdio:

```sh
.venv/bin/python -m komfovent_mcp
```

Environment variables (defaults shown):

| Variable | Default |
| --- | --- |
| `KOMFOVENT_HOST` | `192.168.0.60` |
| `KOMFOVENT_PORT` | `502` |
| `KOMFOVENT_UNIT_ID` | `1` |
| `KOMFOVENT_TIMEOUT` | `5` |
| `KOMFOVENT_MIN_GAP_S` | `0.5` |

## Cursor

Add the server to Cursor MCP settings. An example is in [config/cursor-mcp.example.json](config/cursor-mcp.example.json):

```json
{
  "mcpServers": {
    "komfovent": {
      "command": ".venv/bin/python",
      "args": ["-m", "komfovent_mcp"],
      "env": {
        "KOMFOVENT_HOST": "192.168.0.60",
        "KOMFOVENT_PORT": "502",
        "KOMFOVENT_UNIT_ID": "1"
      }
    }
  }
}
```

The SDK entry point is `MCPServer` from `mcp.server.mcpserver` (the mcp 2 successor of FastMCP).
