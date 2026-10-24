"""Logs tagged from a module-level variable: after an await, it may hold another request's id."""

import asyncio

current_request = "-"  # one variable for the whole process, shared by every request
start = 0.0


def log(message, written_by):
    ms = round((asyncio.get_running_loop().time() - start) * 100) * 10
    print(f"{ms:4} ms  [{current_request}] {message:26} (written by {written_by}'s handler)")


async def handle(shopper, arrives_ms):
    global current_request
    await asyncio.sleep(arrives_ms / 1000)
    current_request = shopper  # "set the request id at the start of the handler"
    log("asking seller-b", shopper)
    await asyncio.sleep(0.12)  # seller-b's 120 ms; other requests run here
    log("seller-b answered 1,199", shopper)


async def main():
    global start
    start = asyncio.get_running_loop().time()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(handle("shopper-1", 0))
        tg.create_task(handle("shopper-2", 50))


if __name__ == "__main__":
    asyncio.run(main())
