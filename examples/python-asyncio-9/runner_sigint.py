"""What asyncio.Runner does with SIGINT (Ctrl-C), and with SIGTERM, which it does not handle."""

import asyncio
import signal
import subprocess
import sys
import time


async def main():
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        print("main task: CancelledError at its await", flush=True)
        raise
    finally:
        print("main task: finally ran", flush=True)


def child():
    print("ready", flush=True)
    try:
        with asyncio.Runner() as runner:  # asyncio.run(main()) is this, in one line
            runner.run(main())
    except KeyboardInterrupt:
        print("runner.run raised KeyboardInterrupt", flush=True)


def parent(sig):
    proc = subprocess.Popen([sys.executable, __file__, "child"], stdout=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "ready"
    time.sleep(0.2)
    proc.send_signal(sig)
    proc.wait(timeout=5)
    print(f"{sig.name}: return code {proc.returncode}")
    for line in proc.communicate()[0].splitlines():
        print(f"    {line}")


if __name__ == "__main__":
    if sys.argv[1:] == ["child"]:
        child()
    else:
        parent(signal.SIGINT)
        parent(signal.SIGTERM)
