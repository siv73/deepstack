"""SIGTERM and an asyncio program. Each case runs as its own process.

The child may start one 300 ms job (a stand-in for a request in flight), then waits to be
told to stop. The parent sends SIGTERM at 100 ms and SIGKILL if the child is still running
at 2 s. The child prints when it saw the stop request.
"""

import asyncio
import signal
import subprocess
import sys
import time


async def job(log):
    try:
        await asyncio.sleep(0.3)
        log("job finished")
    finally:
        log("job's finally ran")


async def child(way, with_job):
    loop = asyncio.get_running_loop()
    start = loop.time()

    def log(text):
        print(f"{round((loop.time() - start) * 100) * 10} ms {text}", flush=True)

    stop = asyncio.Event()
    if way == "add_signal_handler":
        loop.add_signal_handler(signal.SIGTERM, stop.set)  # a callback on the loop
    elif way == "signal.signal":
        signal.signal(signal.SIGTERM, lambda signum, frame: stop.set())  # runs between bytecodes
    task = asyncio.create_task(job(log)) if with_job else None
    print("ready", flush=True)
    await stop.wait()
    log("stop seen")
    if task:
        await task
    log("exit")


def parent(way, with_job):
    proc = subprocess.Popen([sys.executable, __file__, way, str(with_job)], stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "ready"
    time.sleep(0.1)
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=1.9)
        how = "exited"
    except subprocess.TimeoutExpired:
        proc.kill()  # the grace period is over
        proc.wait()
        how = "SIGKILL at 2 s"
    lines = proc.communicate()[0].splitlines()
    print(f"{way}, {'a job in flight' if with_job else 'idle'}: {how}, return code {proc.returncode}")
    for line in lines:
        print(f"    {line}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(child(sys.argv[1], sys.argv[2] == "True"))
    else:
        parent("no handler", True)
        parent("add_signal_handler", True)
        parent("add_signal_handler", False)
        parent("signal.signal", True)
        parent("signal.signal", False)
