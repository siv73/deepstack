"""Three shutdowns that never finish, and the same three fixed. Each runs as its own process.

The child handles SIGTERM with add_signal_handler, and main() returns when it arrives, so
asyncio.run starts its own clean-up. The parent sends SIGTERM at 200 ms and SIGKILL if the
child is still running 1.5 s later.
"""

import asyncio
import signal
import subprocess
import sys
import time


def log(text):
    print(text, flush=True)


async def refuses_cancel(fixed):
    while True:
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            log("background task: cancelled")
            if fixed:
                raise  # the fix: let the cancellation finish the Task
            log("background task: ignoring it and carrying on")  # Part 4's trap 5


async def idle_client_handler(reader, writer):
    await reader.readline()  # a client that connects and never sends: waits here
    writer.close()


async def main(case, fixed):
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    loop.add_signal_handler(signal.SIGTERM, stop.set)
    keep = []
    if case == "a Task that refuses to be cancelled":
        keep.append(asyncio.create_task(refuses_cancel(fixed)))
        log("ready")
        await stop.wait()
        log("main returns; asyncio.run cancels what is left")
    elif case == "a connection that never closes":
        server = await asyncio.start_server(idle_client_handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        keep.append(await asyncio.open_connection("127.0.0.1", port))  # the idle keep-alive client
        log("ready")
        async with server:
            await stop.wait()
            log("leaving async with server: close(), then wait_closed()")
            if fixed:
                server.close()
                server.close_clients()  # 3.13+: close the open connections too
                async with asyncio.timeout(0.5):
                    await server.wait_closed()
    else:  # a thread that is still running
        seconds = 0.3 if fixed else 30  # the fix: the call's own time limit, passed down (Part 5)
        keep.append(loop.run_in_executor(None, time.sleep, seconds))
        log("ready")
        await stop.wait()
        log("main returns; asyncio.run waits for the default executor's threads")


def parent(case, fixed):
    start = time.monotonic()
    proc = subprocess.Popen([sys.executable, __file__, case, str(fixed)], stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "ready"
    time.sleep(0.2)
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        proc.kill()  # the grace period is over
        proc.wait()
    ms = round((time.monotonic() - start) * 10) * 100
    outcome = "SIGKILL" if proc.returncode == -signal.SIGKILL else f"exit {proc.returncode}"
    print(f"{case}{' (fixed)' if fixed else ''}: {outcome} after about {ms} ms")
    for line in proc.communicate()[0].splitlines():
        print(f"    {line}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(main(sys.argv[1], sys.argv[2] == "True"))
        log("asyncio.run returned")
    else:
        for case in (
            "a Task that refuses to be cancelled",
            "a connection that never closes",
            "a thread that is still running",
        ):
            parent(case, fixed=False)
            parent(case, fixed=True)
