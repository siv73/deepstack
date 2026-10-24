"""What gateway v9's shutdown relies on, checked on whichever Python runs this file."""

import asyncio
import inspect
import sys


async def wait_closed_with_an_open_connection():
    async def handler(reader, writer):
        await reader.readline()  # an idle client: never sends
        writer.close()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    _, writer = await asyncio.open_connection("127.0.0.1", server.sockets[0].getsockname()[1])
    await asyncio.sleep(0.05)
    server.close()
    try:
        async with asyncio.timeout(0.2):
            await server.wait_closed()
        result = "returns at once"
    except TimeoutError:
        result = "waits for the open connection"
    writer.close()
    return result


async def main():
    print(f"Python {sys.version_info[0]}.{sys.version_info[1]}")
    print(f"Server.close_clients(): {hasattr(asyncio.Server, 'close_clients')}")
    waits = await wait_closed_with_an_open_connection()
    print(f"Server.wait_closed() after close(), one connection open: {waits}")
    print(f"Queue.shutdown(): {hasattr(asyncio.Queue, 'shutdown')}")
    timeout = "timeout" in inspect.signature(asyncio.get_running_loop().shutdown_default_executor).parameters
    print(f"shutdown_default_executor(timeout=...): {timeout}")
    print(f"asyncio.Runner: {hasattr(asyncio, 'Runner')}")


asyncio.run(main())
