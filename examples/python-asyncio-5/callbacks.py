"""call_soon and call_later: the two ways to put a callback on asyncio's loop."""

import asyncio


async def main():
    loop = asyncio.get_running_loop()
    start = loop.time()  # the loop's own monotonic clock, in seconds

    def say(what):
        ms = round((loop.time() - start) * 100) * 10
        print(f"{ms:4} ms  {what}")

    loop.call_later(0.2, say, "call_later(0.2)")
    loop.call_later(0.1, say, "call_later(0.1)")
    soon = loop.call_soon(say, "call_soon, first")
    loop.call_soon(say, "call_soon, second")
    handle = loop.call_later(0.15, say, "never printed")
    handle.cancel()  # a cancelled handle is skipped
    print(f"call_soon returned a {type(soon).__name__}; call_later returned a {type(handle).__name__}")
    await asyncio.sleep(0.3)


asyncio.run(main())
