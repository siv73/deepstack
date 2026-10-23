"""What one waiting request costs the gateway in memory, at the least: its connection and its Task.

1,000 shoppers connect from a separate process and send a request line. Each request is
read, then parked in a line it never leaves, the way a request waits when work arrives
faster than it can be done. tracemalloc counts the Python memory the 1,000 requests hold.
"""

import asyncio
import subprocess
import sys
import tracemalloc

WAITING = 1_000

SHOPPERS = """
import socket, sys, time
port, n = int(sys.argv[1]), int(sys.argv[2])
socks = []
for i in range(n):
    s = socket.create_connection(("127.0.0.1", port))
    s.sendall(f"shopper-{i} kettle-1l\\n".encode())
    socks.append(s)
print("sent", flush=True)
time.sleep(30)  # keep every connection open until killed
"""


async def main():
    line = asyncio.get_running_loop().create_future()  # a line nobody is served from
    arrived = 0

    async def serve(reader, writer):
        nonlocal arrived
        await reader.readline()  # the request
        arrived += 1
        await asyncio.shield(line)  # wait for a turn that never comes

    server = await asyncio.start_server(serve, "127.0.0.1", 0, backlog=WAITING)
    port = server.sockets[0].getsockname()[1]
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    shoppers = subprocess.Popen(
        [sys.executable, "-c", SHOPPERS, str(port), str(WAITING)], stdout=subprocess.PIPE, text=True
    )
    while arrived < WAITING:
        await asyncio.sleep(0.05)
    held = tracemalloc.get_traced_memory()[0] - before
    tracemalloc.stop()
    shoppers.kill()
    shoppers.wait()
    shoppers.stdout.close()
    each = held / WAITING / 1024
    print(f"{WAITING:,} requests waiting hold {held / 1024 / 1024:.1f} MB of Python memory")
    print(f"one waiting request: about {each:.0f} KB (its connection, buffers and Task)")
    server.close()
    line.cancel()


if __name__ == "__main__":
    asyncio.run(main())
