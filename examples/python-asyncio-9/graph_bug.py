"""Rung 4: the call graph of seller-e's fill, after the request that waited for it through shield() ended.

On Python 3.14.0 to 3.14.7, shield() leaves the finished waiter in the fill's awaited-by set, and
format_call_graph() then raises AttributeError (fixed in 3.14.8: gh-155143 and gh-156408).
"""

import asyncio
import sys

from gateway_v9 import Budget
from stubs import make_gateway
from virtual_clock import VirtualClockLoop


async def main():
    gateway = make_gateway()
    await gateway.start()
    answer = await gateway.compare("kettle-1l")  # 250 ms: answered without seller-e
    fill = gateway.flights.flights[("seller-e", "kettle-1l")]  # still running: 900 ms in all
    graph = asyncio.capture_call_graph(fill)
    waiters = [(g.future.get_name(), "done" if g.future.done() else "running") for g in graph.awaited_by]
    print(f"Python {'.'.join(map(str, sys.version_info[:3]))}; answer at {answer.ms} ms without seller-e")
    print(f"the fill's awaited-by entries after the request ended: {waiters}")
    try:
        asyncio.format_call_graph(fill)
        print("format_call_graph(fill): printed")
    except AttributeError as exc:
        print(f"format_call_graph(fill): AttributeError: {exc}")
    await gateway.shutdown([], Budget())


asyncio.run(main(), loop_factory=VirtualClockLoop)
