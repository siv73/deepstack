"""Clean-up in finally runs after a cancel, may await, and is cut short only by a second cancel."""

import asyncio


async def ask_seller_e(log, clock):
    try:
        await asyncio.sleep(0.9)  # seller-e's answer, never reached
    except asyncio.CancelledError:
        log(clock(), "CancelledError arrived: log it, then let it travel on")
        raise
    finally:
        log(clock(), "finally: closing the connection (an await)")
        await asyncio.sleep(0.02)  # like await writer.wait_closed() on a slow network
        log(clock(), "finally: connection closed")


async def run(title, cancels_at):
    loop = asyncio.get_running_loop()
    start = loop.time()

    def clock():
        return round((loop.time() - start) * 100) * 10

    def log(ms, text):
        print(f"{ms:5} ms  {text}")

    print(f"-- {title} --")
    task = asyncio.create_task(ask_seller_e(log, clock))
    for at in cancels_at:
        loop.call_at(start + at, task.cancel)
    await asyncio.wait([task])
    log(clock(), f"task done, cancelled={task.cancelled()}")


async def main():
    await run("one cancel at 250 ms", [0.25])
    await run("a second cancel at 260 ms, during the clean-up", [0.25, 0.26])


asyncio.run(main())
