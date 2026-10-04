"""On SIGTERM: stop taking work, finish what is in flight, exit 0 (Unix, 3.13+)."""

import asyncio
import signal
import sys


async def main(handle_sigterm: bool) -> None:
    stop = asyncio.Event()
    if handle_sigterm:
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
    queue: asyncio.Queue[int] = asyncio.Queue()
    for job in range(6):
        queue.put_nowait(job)

    async def worker() -> None:
        while True:
            try:
                job = await queue.get()
            except asyncio.QueueShutDown:
                return
            try:
                await asyncio.sleep(0.3)  # the job we already took
                print(f"finished job {job}", flush=True)
            finally:
                queue.task_done()

    async with asyncio.TaskGroup() as tg:
        for _ in range(2):
            tg.create_task(worker())
        print("ready", flush=True)
        await stop.wait()
        queue.shutdown(immediate=True)  # drop queued jobs; in-flight ones finish
    print("exited cleanly", flush=True)


if __name__ == "__main__":
    asyncio.run(main(handle_sigterm="--no-handler" not in sys.argv))
