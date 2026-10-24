"""Each Task runs in a copy of the context that was current when the Task was created."""

import asyncio
import contextvars

request_id = contextvars.ContextVar("request_id", default="-")


async def child(label):
    print(f"{label:46} sees {request_id.get()}")
    request_id.set("set by the child")  # changes the child's copy only


def callback(label):
    print(f"{label:46} sees {request_id.get()}")


async def handler():
    request_id.set("shopper-1")
    await asyncio.create_task(child("1. Task created after set('shopper-1')"))
    print(f"{'2. the handler, after the child set its value':46} sees {request_id.get()}")

    late = asyncio.create_task(child("3. Task created before set('shopper-2')"))
    request_id.set("shopper-2")
    await late

    asyncio.get_running_loop().call_soon(callback, "4. call_soon callback")
    await asyncio.sleep(0)

    fresh = asyncio.create_task(child("5. Task given context=Context()"), context=contextvars.Context())
    await fresh
    print(f"{'6. that Task kept its own value':46} {fresh.get_context()[request_id]}")


async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(handler())
    print(f"{'7. main(), which never set a value':46} sees {request_id.get()}")


if __name__ == "__main__":
    asyncio.run(main())
