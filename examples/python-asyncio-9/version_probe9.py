"""What this page's tools need, checked on whichever Python runs this file."""

import asyncio
import importlib.util
import inspect
import sys
import time
import unittest

from virtual_clock import VirtualClockLoop


async def nap():
    await asyncio.sleep(0.9)
    return asyncio.get_running_loop().time()


print(f"Python {sys.version_info[0]}.{sys.version_info[1]}")
print(f"asyncio.format_call_graph(): {hasattr(asyncio, 'format_call_graph')}")
print(f"python -m asyncio ps / pstree: {importlib.util.find_spec('asyncio.tools') is not None}")
print(f"Task.get_stack(): {hasattr(asyncio.Task, 'get_stack')}")
print(f"asyncio.run(..., loop_factory=): {'loop_factory' in inspect.signature(asyncio.run).parameters}")
print(f"IsolatedAsyncioTestCase.loop_factory: {hasattr(unittest.IsolatedAsyncioTestCase, 'loop_factory')}")
started = time.perf_counter()
with asyncio.Runner(loop_factory=VirtualClockLoop) as runner:  # Runner: 3.11+
    clock = runner.run(nap())
fast = time.perf_counter() - started < 0.5
print(f"virtual clock through asyncio.Runner: sleep(0.9) ends at {clock} s, in under 0.5 s real: {fast}")
