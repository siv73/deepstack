"""A queue that hides overload: every request is accepted, and every answer comes too late.

5 workers, 50 ms a request: 100 requests a second. 150 a second arrive for 2 seconds.
Each request has a 250 ms budget from the moment it arrives.
"""

import asyncio

WORKERS, SERVICE_S, ARRIVALS_PER_S, SECONDS, BUDGET_S = 5, 0.050, 150, 2, 0.250


async def run(maxsize, check_deadline):
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize)
    on_time = late = busy = stale = 0
    longest_wait = 0.0

    async def worker():
        nonlocal on_time, late, stale, longest_wait
        while True:
            arrived = await queue.get()
            try:
                waited = loop.time() - arrived
                longest_wait = max(longest_wait, waited)
                if check_deadline and waited + SERVICE_S > BUDGET_S:
                    stale += 1  # cannot finish in time: drop it before doing the work
                    continue
                await asyncio.sleep(SERVICE_S)
                if loop.time() - arrived <= BUDGET_S:
                    on_time += 1
                else:
                    late += 1
            finally:
                queue.task_done()

    pool = [asyncio.create_task(worker()) for _ in range(WORKERS)]
    start = loop.time()
    total = ARRIVALS_PER_S * SECONDS
    for n in range(total):
        await asyncio.sleep(max(0.0, start + n / ARRIVALS_PER_S - loop.time()))
        try:
            queue.put_nowait(loop.time())
        except asyncio.QueueFull:
            busy += 1  # refused at once: the caller hears "busy" in about 0 ms
    depth = queue.qsize()
    await queue.join()
    for t in pool:
        t.cancel()
    await asyncio.wait(pool)
    label = f"maxsize={maxsize}" + (", deadline checked" if check_deadline else "")
    print(f"{label}: {total} arrived; on time {on_time}, late {late}, dropped stale {stale}, busy {busy}")
    wait_ms = round(longest_wait * 100) * 10
    print(f"  queue depth when arrivals stopped: {depth}; longest wait in the queue {wait_ms} ms")


async def main():
    await run(maxsize=10_000, check_deadline=False)
    await run(maxsize=10, check_deadline=True)


asyncio.run(main())
