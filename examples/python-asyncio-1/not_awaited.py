"""The most common async bug: calling a coroutine function without await."""


async def send_receipt(outbox: list[str], order_id: int) -> None:
    outbox.append(f"receipt for {order_id}")


async def checkout_buggy(outbox: list[str]) -> None:
    send_receipt(outbox, 42)  # creates a coroutine object, runs nothing


async def checkout_fixed(outbox: list[str]) -> None:
    await send_receipt(outbox, 42)
