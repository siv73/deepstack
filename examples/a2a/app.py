"""Wiring: serve the card at the well-known path and JSON-RPC at /a2a."""

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from card import CARD
from refund_agent import RefundAgent
from starlette.applications import Starlette

handler = DefaultRequestHandler(
    agent_executor=RefundAgent(),
    task_store=InMemoryTaskStore(),  # production: a database-backed TaskStore
    agent_card=CARD,
)
app = Starlette(
    routes=[
        *create_agent_card_routes(CARD),  # GET /.well-known/agent-card.json
        *create_jsonrpc_routes(handler, rpc_url="/a2a"),
    ]
)
