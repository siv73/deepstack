"""Proves every behaviour the MCP page claims about orders_server.py (in memory, no network)."""

import pytest
from mcp import Client, MCPError
from mcp.types import ElicitResult, InputRequiredResult
from orders_server import mcp
from refunds import REFUNDED


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_refunds():
    REFUNDED.clear()


async def accept(context, params) -> ElicitResult:
    return ElicitResult(action="accept", content={"ok": True})


async def decline(context, params) -> ElicitResult:
    return ElicitResult(action="decline")


@pytest.mark.anyio
async def test_speaks_2026_07_28():
    async with Client(mcp) as client:
        assert client.protocol_version == "2026-07-28"


@pytest.mark.anyio
async def test_tools_list_exposes_schema_generated_from_type_hints():
    async with Client(mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
        assert set(tools) == {"get_order", "refund_order"}
        schema = tools["get_order"].input_schema
        assert schema["properties"]["order_id"]["type"] == "string"
        assert schema["required"] == ["order_id"]
        # The resolver-filled parameter is not something the model can supply.
        assert "confirm" not in tools["refund_order"].input_schema["properties"]


@pytest.mark.anyio
async def test_unknown_order_is_a_tool_execution_error_not_a_protocol_error():
    async with Client(mcp) as client:
        result = await client.call_tool("get_order", {"order_id": "ord_9"})
        assert result.is_error is True
        assert "IDs look like ord_1001" in result.content[0].text


@pytest.mark.anyio
async def test_known_order_returns_structured_content():
    async with Client(mcp) as client:
        result = await client.call_tool("get_order", {"order_id": "ord_1001"})
        assert result.is_error is False
        assert result.structured_content == {"status": "delivered", "amount_inr": 1499}


@pytest.mark.anyio
async def test_first_round_is_input_required_with_opaque_state():
    async with Client(mcp, elicitation_callback=accept) as client:
        first = await client.session.call_tool(
            "refund_order", {"order_id": "ord_1001"}, allow_input_required=True
        )
        assert isinstance(first, InputRequiredResult)
        (request,) = first.input_requests.values()
        assert request.method == "elicitation/create"
        assert first.request_state  # sealed by the SDK; the client must echo it unchanged
        assert "ord_1001" not in REFUNDED  # nothing happened yet


@pytest.mark.anyio
async def test_client_retries_with_answer_and_refund_happens():
    async with Client(mcp, elicitation_callback=accept) as client:
        result = await client.call_tool("refund_order", {"order_id": "ord_1001"})
        assert result.content[0].text == "Refunded ord_1001."
        assert "ord_1001" in REFUNDED


@pytest.mark.anyio
async def test_declined_confirmation_means_no_refund():
    async with Client(mcp, elicitation_callback=decline) as client:
        result = await client.call_tool("refund_order", {"order_id": "ord_1001"})
        assert "not approved" in result.content[0].text
        assert "ord_1001" not in REFUNDED


@pytest.mark.anyio
async def test_client_without_elicitation_support_fails_loudly():
    async with Client(mcp) as client:
        with pytest.raises(MCPError, match="did not declare the form elicitation capability"):
            await client.call_tool("refund_order", {"order_id": "ord_1001"})


@pytest.mark.anyio
async def test_small_refund_needs_no_round_trip():
    async with Client(mcp) as client:  # no elicitation support declared, and none needed
        first = await client.session.call_tool(
            "refund_order", {"order_id": "ord_1002"}, allow_input_required=True
        )
        assert not isinstance(first, InputRequiredResult)
        assert first.content[0].text == "Refunded ord_1002."
