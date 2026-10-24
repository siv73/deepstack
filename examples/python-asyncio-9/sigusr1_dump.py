"""Rung 3: kill -USR1 makes gateway v10 print every Task and where it waits, from inside the process.

On 3.14 each Task's whole await chain (format_call_graph); on 3.11 to 3.13 its one frame.
Works where the ps tool cannot run: no permission to read another process, or an older Python.
"""

import asyncio
import io
import os
import re
import signal
import sys

import gateway_v10
from gateway_v9 import Budget
from stubs import StallingAuditStore, connection, make_gateway
from virtual_clock import VirtualClockLoop


def tidy(text):
    """The same on every machine: no ids, no directories, no line numbers inside asyncio itself."""
    text = re.sub(r"0x[0-9a-f]+", "0x…", text)
    text = re.sub(r"""File (['"])[^'"]*/asyncio/([\w.]+)\1, line \d+""", r"File \1asyncio/\2\1", text)
    text = re.sub(r"/[^\s'\"<>]*/asyncio/([\w.]+\.py)(:\d+)?", r"asyncio/\1", text)
    return re.sub(r"/[^\s'\"<>]*/([\w.]+\.py)", r"\1", text)


async def main():
    out = io.StringIO()
    store = StallingAuditStore()
    gateway = make_gateway(store=store, writers=1)
    await gateway.start()
    gateway_v10.install_dump_on_sigusr1(out)
    store.answering.clear()
    request = asyncio.create_task(gateway.serve(*connection("shop-7 kettle-1l")))
    await asyncio.sleep(0.5)  # stuck in its audit wait (the deadline is 1 s)
    os.kill(os.getpid(), signal.SIGUSR1)  # what an operator does from a shell: kill -USR1 <pid>
    await asyncio.sleep(0.01)  # the handler runs as a loop callback, on a later iteration
    store.answering.set()
    await request
    await gateway.shutdown([], Budget())
    dump = tidy(out.getvalue())
    count, rest = dump.split("\n", 1)
    print(f"Python {sys.version_info[0]}.{sys.version_info[1]}: the dump lists {count}; two of them:")
    for block in re.split(r"\n(?=\* )", rest):
        if block.startswith(
            ("* Task(name='shop-7", "* Task(name='audit-writer", "* shop-7", "* audit-writer")
        ):
            print(block.rstrip())


asyncio.run(main(), loop_factory=VirtualClockLoop)
