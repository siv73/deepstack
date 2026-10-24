"""Rung 2: the same incident with debug mode on. What does asyncio report about the stuck requests?"""

import asyncio
import logging
import time

import incident


class Collect(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


async def look(gateway):
    loop = asyncio.get_running_loop()
    loop.slow_callback_duration = 0.05  # report any step of 50 ms or more, as Part 4 set it for CI
    heard = Collect()
    logging.getLogger("asyncio").addHandler(heard)
    await asyncio.sleep(0.5)  # 5 requests stuck, the whole time
    stuck = len(heard.records)
    loop.call_soon(time.sleep, 0.2)  # for comparison: one callback that blocks the loop for 200 ms
    await asyncio.sleep(0.3)
    logging.getLogger("asyncio").removeHandler(heard)
    blocked = [r.getMessage().split(" took ")[1] for r in heard.records[stuck:]]
    return [
        f"debug mode: {loop.get_debug()}; slow_callback_duration: {loop.slow_callback_duration} s",
        f"asyncio log records in 500 ms with 5 requests stuck: {stuck}",
        f"asyncio log records after one 200 ms blocking callback: {len(blocked)} (took {blocked[0]})",
    ]


if __name__ == "__main__":
    report, seen, _ = incident.main(look, debug=True)
    print("\n".join(seen))
    print(report[1])
