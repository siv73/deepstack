"""A sync library calls you back on its own thread. Hand the work to the loop safely."""

import asyncio
import threading


def consume_in_thread(loop: asyncio.AbstractEventLoop, handle, messages) -> threading.Thread:
    def run() -> None:  # e.g. a sync Kafka/MQ client's consumer thread
        for msg in messages:
            fut = asyncio.run_coroutine_threadsafe(handle(msg), loop)
            fut.result(timeout=5)  # wait for the async handler: natural backpressure

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def notify_from_thread(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue, item) -> None:
    loop.call_soon_threadsafe(queue.put_nowait, item)  # never queue.put_nowait directly
