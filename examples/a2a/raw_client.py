"""A client with no SDK: plain JSON-RPC over HTTP, to show what goes on the wire."""

import uuid

import httpx

HEADERS = {"A2A-Version": "1.0"}  # without it, the agent must assume 0.3


async def fetch_card(http: httpx.AsyncClient) -> dict:
    return (await http.get("/.well-known/agent-card.json")).json()


async def send(http: httpx.AsyncClient, text: str, task: dict | None = None) -> dict:
    message = {"messageId": str(uuid.uuid4()), "role": "ROLE_USER", "parts": [{"text": text}]}
    if task:  # continue an existing task: same taskId and contextId
        message |= {"taskId": task["id"], "contextId": task["contextId"]}
    body = {"jsonrpc": "2.0", "id": 1, "method": "SendMessage", "params": {"message": message}}
    return (await http.post("/a2a", json=body, headers=HEADERS)).json()
