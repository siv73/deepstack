"""What happens between await reader.readline() and your code resuming, made visible."""

import asyncio

from sellers_net import running_sellers
from tracing import TracingSelector


async def main(port):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(b"kettle-1l\n")
    await writer.drain()
    print("task: calling await reader.readline()")
    TracingSelector.printing = True
    line = await reader.readline()
    TracingSelector.printing = False
    print(f"task: resumed with {line.decode().strip()!r}")
    writer.close()
    await writer.wait_closed()


TracingSelector.printing = False  # only trace the readline() wait
with running_sellers() as ports:
    asyncio.run(main(ports["seller-b"]), loop_factory=lambda: asyncio.SelectorEventLoop(TracingSelector()))
