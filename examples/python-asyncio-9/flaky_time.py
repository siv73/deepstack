"""Rung 4: one assertion, 'the answer comes at 250 ms, within 30 ms', on a real and on a virtual clock.

'Busy machine' is a 60 ms stall of the loop's thread just before the deadline: what a CI runner
sharing its CPU with other jobs does to a test now and then.
"""

import asyncio
import time

from gateway_v9 import Budget
from stubs import make_gateway
from virtual_clock import VirtualClockLoop


async def answer_ms(busy):
    gateway = make_gateway()
    await gateway.start()
    if busy:
        asyncio.get_running_loop().call_later(0.24, time.sleep, 0.06)  # the stall
    answer = await gateway.compare("kettle-1l")
    await gateway.shutdown([], Budget(fills=0.0))  # don't wait for seller-e: one answer is measured
    return answer.ms


for clock, factory in (("real clock", asyncio.EventLoop), ("virtual clock", VirtualClockLoop)):
    for machine, busy in (("quiet machine", False), ("busy machine", True)):
        started = time.perf_counter()
        ms = asyncio.run(answer_ms(busy), loop_factory=factory)
        took = round((time.perf_counter() - started) * 1000, -1)
        verdict = "pass" if abs(ms - 250) <= 30 else "FAIL"
        print(f"{clock:<13} {machine:<13} answered at {ms} ms -> {verdict}   (the test took {took:.0f} ms)")
