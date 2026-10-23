"""Signal handlers can only be set from the main thread. A loop run in another thread cannot set one."""

import asyncio
import signal
import threading


async def try_add_handler():
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, lambda: None)
        return "set"
    except (RuntimeError, ValueError) as exc:
        return f"{type(exc).__name__}: {exc}"


def in_thread(results):
    results["asyncio.run in a worker thread, add_signal_handler"] = asyncio.run(try_add_handler())
    try:
        signal.signal(signal.SIGTERM, lambda signum, frame: None)
        results["signal.signal in a worker thread"] = "set"
    except ValueError as exc:
        results["signal.signal in a worker thread"] = f"ValueError: {exc}"
    with asyncio.Runner() as runner:  # Runner installs its Ctrl-C handler only in the main thread
        runner.run(asyncio.sleep(0))
        handler = signal.getsignal(signal.SIGINT).__name__
        results["Runner in a worker thread, SIGINT handler afterwards"] = handler


results = {"asyncio.run in the main thread, add_signal_handler": asyncio.run(try_add_handler())}
worker = threading.Thread(target=in_thread, args=(results,))
worker.start()
worker.join()
for what, outcome in results.items():
    print(f"{what}: {outcome}")
