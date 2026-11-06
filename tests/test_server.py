import json

from komfovent_mcp.client import KomfoventClient
from komfovent_mcp.config import Config
from komfovent_mcp.server import build_server
from tests.fake_modbus import FakeModbus


def _payload(result) -> dict:
    if result.structured_content:
        content = result.structured_content
        if set(content) == {"result"}:
            return content["result"]
        return content
    return json.loads(result.content[0].text)


async def test_server_registers_tools_and_resources() -> None:
    server = build_server(KomfoventClient(Config(min_gap_s=0), modbus=FakeModbus()))
    tools = {tool.name for tool in await server.list_tools()}
    assert tools == {
        "get_status",
        "set_power",
        "set_mode",
        "set_temperature",
        "set_eco",
        "set_auto",
        "get_alarms",
        "reset_alarms",
        "get_energy",
        "set_mode_settings",
        "reset_filters",
    }
    resources = {str(item.uri) for item in await server.list_resources()}
    assert resources == {
        "komfovent://status",
        "komfovent://alarms",
        "komfovent://energy",
    }


async def test_get_status_tool_reads_through_the_client() -> None:
    modbus = FakeModbus({1: 1, 5: 2, 1000: 0x0120, 1001: 0x3004})
    server = build_server(KomfoventClient(Config(min_gap_s=0), modbus=modbus))
    result = await server.call_tool("get_status", {})
    assert result.is_error is False
    status = _payload(result)
    assert status["power"] is True
    assert status["mode"] == "normal"
    assert status["controller"] == "c6"
    assert status["firmware"] == "1.2.3.4"


async def test_status_resource_matches_the_tool() -> None:
    modbus = FakeModbus({1: 1, 5: 1})
    server = build_server(KomfoventClient(Config(min_gap_s=0), modbus=modbus))
    contents = await server.read_resource("komfovent://status")
    body = contents[0].content
    if isinstance(body, bytes):
        body = body.decode()
    status = json.loads(body) if isinstance(body, str) else body
    assert status["mode"] == "away"
