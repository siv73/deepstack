"""Rung 4: what gateway v10's own telemetry costs at 10 times the load, and what a hostile id does to logs."""

import asyncio
import logging

from gateway_v9 import Budget
from observe import json_lines
from request_log import Lines, request_id
from stubs import make_gateway
from virtual_clock import VirtualClockLoop


async def one_cached_request():
    lines = json_lines("gateway")
    gateway = make_gateway()
    await gateway.start()
    await gateway.compare("kettle-1l")  # fill the cache first: most requests in production are hits
    await asyncio.sleep(1.0)
    lines.lines.clear()
    await gateway.handle("shop-12345", "kettle-1l", asyncio.get_running_loop().time())
    per_request = list(lines.lines)
    await gateway.shutdown([], Budget())
    return per_request


per_request = asyncio.run(one_cached_request(), loop_factory=VirtualClockLoop)
size = sum(len(line.encode()) + 1 for line in per_request)  # + 1 for the newline
print(f"log lines per cached request: {len(per_request)}, {size} bytes")
for label, rate in (("today, 8 processes x 2,000", 16_000), ("at 10 times the load", 160_000)):
    per_second = rate * size / 1e6
    print(f"  {label}: {rate * len(per_request):,} lines a second, {per_second:.1f} MB a second, "
          f"{per_second * 86_400 / 1e6:.2f} TB a day")  # fmt: skip

series = 5 * 4  # seller x outcome (answered, timed out, failed, skipped)
print(f"seller-call counters by seller and outcome: {series} series per process")
print(f"  add an item label, 50,000 items: {series * 50_000:,} series per process")

hostile = 'abc\n{"event":"refund approved","request_id":"admin"}'  # an id taken from a request header
request_id.set(hostile)
text = Lines()  # Part 7's text format
logging.getLogger("demo").handlers = [text]
logging.getLogger("demo").propagate = False
logging.getLogger("demo").warning("audit row not confirmed")
as_json = json_lines("demo")
logging.getLogger("demo").warning("audit row not confirmed")
print(f"a request id with a newline in it: text format writes {len(text.lines[0].splitlines())} lines:")
for line in text.lines[0].splitlines():
    print(f"  {line}")
print(f"JSON format writes {len(as_json.lines[0].splitlines())} line:")
print(f"  {as_json.lines[0]}")
