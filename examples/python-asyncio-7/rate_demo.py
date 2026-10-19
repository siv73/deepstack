"""seller-d allows 20 calls per second with bursts of 5. Ask it 50 times in one second, evenly."""

import asyncio

from ratelimit import TokenBucket


async def main():
    loop = asyncio.get_running_loop()
    start = loop.time()
    bucket = TokenBucket(rate=20, burst=5)
    pattern = ""
    for n in range(50):  # one request every 20 ms
        await asyncio.sleep(max(0.0, start + n * 0.020 - loop.time()))
        pattern += "x" if bucket.try_take() else "."
    first_run = len(pattern) - len(pattern.lstrip("x"))
    print("x = call allowed, . = skipped")
    print(pattern)
    allowed = pattern.count("x")
    print(
        f"{allowed} of 50 allowed: the first {first_run} in a row, then 2 in every 5, the rate of 20 a second"
    )


asyncio.run(main())
