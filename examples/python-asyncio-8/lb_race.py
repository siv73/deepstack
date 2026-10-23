"""The race between SIGTERM and the load balancer, with stand-ins for both.

Two backends, "old" and "new", answer "ok <name>" after 50 ms. A stand-in load balancer sends
a request every 10 ms, taking turns between the backends it believes are in service. At
100 ms the old backend is told to stop, and the balancer learns of it only 300 ms later
(its endpoint update). Without a preStop pause the old backend closes its listener at once;
with one, the stop signal reaches it 400 ms later, after the balancer has stopped sending.
"""

import asyncio
from collections import Counter

PROPAGATION = 0.3  # the balancer's view of endpoints lags the stop by this long
STOP_AT = 0.1


async def backend(name):
    async def answer(reader, writer):
        await reader.readline()
        await asyncio.sleep(0.05)
        writer.write(f"ok {name}\n".encode())
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(answer, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


async def call(port):
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
    except ConnectionRefusedError:
        return "refused"
    writer.write(b"price kettle-1l\n")
    await writer.drain()
    line = (await reader.readline()).decode().strip()
    writer.close()
    await writer.wait_closed()
    return line


async def deploy(pre_stop):
    loop = asyncio.get_running_loop()
    (old, old_port), (new, new_port) = await backend("old"), await backend("new")
    endpoints = {"old": old_port, "new": new_port}
    start = loop.time()

    def pod_stop():  # what the kubelet does to the old Pod
        loop.call_later(pre_stop, old.close)  # the preStop pause, then SIGTERM: the listener closes

    loop.call_at(start + STOP_AT, pod_stop)
    loop.call_at(start + STOP_AT + PROPAGATION, endpoints.pop, "old")  # the balancer catches up
    calls = []
    for n in range(80):  # 800 ms of traffic
        names = sorted(endpoints)
        calls.append(asyncio.create_task(call(endpoints[names[n % len(names)]])))
        await asyncio.sleep(0.01)
    results = Counter(await asyncio.gather(*calls))
    for server in (old, new):
        server.close()
        await server.wait_closed()
    print(f"preStop pause {pre_stop * 1000:g} ms: {dict(sorted(results.items()))}")


async def main():
    await deploy(pre_stop=0.0)
    await deploy(pre_stop=0.4)


asyncio.run(main())
