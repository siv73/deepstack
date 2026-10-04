"""The Agent Card: what the refunds agent tells the world about itself."""

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

CARD = AgentCard(
    name="Refund Status Agent",
    description="Looks up the status of a customer refund by order ID.",
    version="1.0.0",
    supported_interfaces=[
        AgentInterface(
            url="https://refunds.example.com/a2a", protocol_binding="JSONRPC", protocol_version="1.0"
        )
    ],
    capabilities=AgentCapabilities(streaming=True, push_notifications=False),
    default_input_modes=["text/plain"],
    default_output_modes=["application/json"],
    skills=[
        AgentSkill(
            id="refund-status",
            name="Refund status",
            description="Given an order ID like ORD-1234, returns where its refund is.",
            tags=["payments", "refunds"],
            examples=["Where is the refund for ORD-1234?"],
        )
    ],
)
