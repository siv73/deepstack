"""A small stand-in for the orchestrator during a deploy.

It starts a gateway process, sends a crowd of shoppers, sends SIGTERM while they are in
flight, tries one more shopper after that, and sends SIGKILL if the process has not exited
within the grace period. It prints what the shoppers got and what the process reported.
"""

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent


async def shopper(port, line, t0):
    """One shopper. Returns (what it got, ms since t0 when it got it)."""
    loop = asyncio.get_running_loop()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
    except OSError as exc:
        return f"refused ({type(exc).__name__})", round((loop.time() - t0) * 100) * 10
    try:
        writer.write(f"{line}\n".encode())
        await writer.drain()
        answer = (await reader.readline()).decode().strip()
    except OSError:
        answer = ""
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
    return answer or "no answer (connection closed)", round((loop.time() - t0) * 100) * 10


def summary(label, results):
    answers = dict(sorted(Counter(a for a, _ in results).items()))
    return f"{len(results)} {label}: {answers}, the last after {max(ms for _, ms in results)} ms"


async def drive(proc, ports, shoppers, quick, sigterm_at, late_at):
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    sale = asyncio.gather(*[shopper(ports[0], f"sale-{n} kettle-1l", t0) for n in range(1, shoppers + 1)])
    fast = asyncio.gather(*[shopper(ports[1], f"quick-{n} kettle-1l", t0) for n in range(1, quick + 1)])
    await asyncio.sleep(sigterm_at)
    proc.send_signal(signal.SIGTERM)
    await asyncio.sleep(late_at - sigterm_at)
    late_result = await shopper(ports[0], "late-1 kettle-1l", t0)
    lines = [summary("shoppers", await sale)]
    if len(ports) > 1:
        lines.append(summary("quick quotes", await fast))
    else:
        fast.cancel()
    lines.append(f"a shopper arriving at {late_at * 1000:g} ms: {late_result[0]}")
    return lines


def deploy(script, *, shoppers=20, quick=5, sigterm_at=0.1, late_at=0.15, grace=3.0):
    proc = subprocess.Popen(
        [sys.executable, script],
        cwd=HERE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,  # its own process group, so its pool workers can be found afterwards
    )
    ports = [int(p) for p in proc.stdout.readline().split()[1:]]  # "ready <port> [<quick port>]"
    quick = quick if len(ports) > 1 else 0
    start = time.monotonic()
    lines = asyncio.run(drive(proc, ports, shoppers, quick, sigterm_at, late_at))
    deadline = start + sigterm_at + grace
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    if proc.poll() is None:
        proc.kill()  # the grace period is over: SIGKILL
        proc.wait()
        how = f"still running {grace:g} s after SIGTERM: SIGKILL"
    else:
        how = "exited by itself"
    with contextlib.suppress(ProcessLookupError):  # remove what the process left behind (pool workers)
        os.killpg(proc.pid, signal.SIGKILL)
    out, err = proc.communicate()
    print(f"SIGTERM at {sigterm_at * 1000:g} ms, while the shoppers were in flight")
    for line in lines:
        print(f"  {line}")
    for line in out.splitlines():
        print(f"  process: {line}")
    print(f"process {how}; return code {proc.returncode}; stderr lines: {len(err.splitlines())}")
