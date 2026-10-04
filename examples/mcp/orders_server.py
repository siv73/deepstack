"""A small MCP server for an orders backend (MCP Python SDK v2, spec 2026-07-28)."""

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

mcp = MCPServer("Orders")


class Order(BaseModel):
    status: str
    amount_inr: int


ORDERS = {
    "ord_1001": Order(status="delivered", amount_inr=1499),
    "ord_1002": Order(status="delivered", amount_inr=299),
}


@mcp.tool()
def get_order(order_id: str) -> Order:
    """Look up one order by its ID, e.g. ord_1001."""
    if order_id not in ORDERS:
        # A tool execution error: the model sees it and can fix its own mistake.
        raise ToolError(f"No order {order_id!r}. IDs look like ord_1001.")
    return ORDERS[order_id]
