"""Calling the loop from another thread: call_soon vs call_soon_threadsafe."""

import asyncio
import threading
import time


def trial(method, debug=False):
    loop = asyncio.new_event_loop()
    loop.set_debug(debug)
    start = loop.time()
    ran_at = []

    def callback():
        ran_at.append(round((loop.time() - start) * 100) * 10)

    def other_thread():
        time.sleep(0.1)  # 100 ms in, another thread hands the loop some work
        try:
            getattr(loop, method)(callback)
        except RuntimeError as e:
            ran_at.append(f"RuntimeError: {e}")

    threading.Thread(target=other_thread).start()
    loop.call_later(1.0, loop.stop)  # the loop's only timer: 1 second away
    loop.run_forever()
    loop.close()
    return ran_at[0] if ran_at else "never"


if __name__ == "__main__":
    print(f"call_soon:            callback ran at {trial('call_soon')} ms (asked at 100 ms)")
    print(f"call_soon_threadsafe: callback ran at {trial('call_soon_threadsafe')} ms (asked at 100 ms)")
    print(f"call_soon, debug mode: {trial('call_soon', debug=True)}")
