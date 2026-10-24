"""Rung 4: two tests that pass alone and fail together. Test A forgets to stop its gateway.

Run 1 shares one loop between the tests (what a session-scoped loop does); run 2 gives each
test its own loop. Run 3 is a module-level Event used by two tests on two different loops.
"""

import asyncio
import logging
from collections import Counter

from gateway_v9 import Budget
from metrics import MetricsSink
from spawn import failures
from stubs import make_gateway
from virtual_clock import VirtualClockLoop


async def test_a():
    gateway = make_gateway()
    gateway.metrics.sink = MetricsSink(down=True)  # the metrics service is down in this test
    await gateway.start()
    answer = await gateway.compare("kettle-1l")
    assert answer.best.price == 1199
    left = Counter(t.get_name() for t in asyncio.all_tasks() - {asyncio.current_task()})
    return f"passes; Tasks it leaves running: {dict(sorted(left.items()))}"  # no stop(): no teardown ran


async def test_b():
    gateway = make_gateway()
    await gateway.start()
    await gateway.compare("toaster-2s")
    await asyncio.sleep(1.0)  # B's own fill for seller-e
    await gateway.shutdown([], Budget())
    if failures:
        return f"FAILS: background failures {dict(failures)}"
    return "passes"


def report(label, a, b):
    print(label)
    print(f"  test A {a}")
    print(f"  test B {b}")


logging.getLogger("gateway.background").addHandler(logging.NullHandler())  # counted, not printed
failures.clear()
with asyncio.Runner(loop_factory=VirtualClockLoop) as shared:  # one loop for both tests
    report("one loop shared by both tests:", shared.run(test_a()), shared.run(test_b()))

failures.clear()
a = asyncio.run(test_a(), loop_factory=VirtualClockLoop)  # each test on its own loop
b = asyncio.run(test_b(), loop_factory=VirtualClockLoop)
report("a fresh loop for each test:", a, b)

ready = asyncio.Event()  # module level: made once, used by every test


async def waits_for_ready():
    try:
        async with asyncio.timeout(0.1):
            await ready.wait()
        return "passes"
    except RuntimeError as exc:
        return f"FAILS: RuntimeError: {exc}".replace(hex(id(ready)), "0x…")
    except TimeoutError:
        return "passes (timed out waiting, as intended)"


print("a module-level asyncio.Event, two tests on two loops:")
for name in ("first", "second"):
    print(f"  {name} test {asyncio.run(waits_for_ready(), loop_factory=VirtualClockLoop)}")
