"""Adds a refund tool that asks a human first, using a resolver (MRTR on 2026-07-28)."""

from typing import Annotated

from mcp.server.mcpserver import AcceptedElicitation, Elicit, ElicitationResult, Resolve
from mcp.server.mcpserver.exceptions import ToolError
from orders_server import ORDERS, mcp
from pydantic import BaseModel

REFUNDED: set[str] = set()


class Confirm(BaseModel):
    ok: bool


async def confirm_refund(order_id: str) -> Confirm | Elicit[Confirm]:
    """Ask a human only when the refund is above INR 500."""
    order = ORDERS.get(order_id)
    if order is None or order.amount_inr <= 500:
        return Confirm(ok=True)
    return Elicit(f"Refund INR {order.amount_inr} for {order_id}?", Confirm)


@mcp.tool()
async def refund_order(
    order_id: str, confirm: Annotated[ElicitationResult[Confirm], Resolve(confirm_refund)]
) -> str:
    """Refund an order. Refunds above INR 500 need a human to confirm."""
    if order_id not in ORDERS:
        raise ToolError(f"No order {order_id!r}.")
    match confirm:
        case AcceptedElicitation(data=Confirm(ok=True)):
            REFUNDED.add(order_id)
            return f"Refunded {order_id}."
        case _:
            return f"Refund for {order_id} not approved."
