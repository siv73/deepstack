"""Debug mode as a detector: run three of the traps with debug=True and read what asyncio says."""

import asyncio
import contextlib
import gc
import io
import logging
import re
import warnings
from pathlib import Path

import trap1_forgotten_await as trap1
import trap2_blocking_io as trap2
import trap3_silent as trap3
from metrics import MetricsClient, MetricsSink
from sellers_net import running_sellers


class Collect(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def where(stack):
    """The last frame of our own code ("file.py:line in function"), skipping asyncio's frames."""
    frame = [f for f in stack if "asyncio" not in Path(f.filename).parts][-1]
    return f"{Path(frame.filename).name}:{frame.lineno} in {frame.name}"


async def slow_step(ports):
    collect = Collect()
    logging.getLogger("asyncio").addHandler(collect)
    await trap2.Blocking(ports).compare("kettle-1l")
    logging.getLogger("asyncio").removeHandler(collect)
    for r in collect.records:
        if r.msg.startswith("Executing"):
            coro = re.search(r"coro=<([\w.]+)\(\)", r.args[0]).group(1)
            print(f"asyncio WARNING: Executing <Task coro={coro}()> took {r.args[1]:.1f} seconds")


async def never_awaited(ports):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with contextlib.redirect_stdout(io.StringIO()):  # hide the per-seller lines
            await trap1.ForgotAwait(ports, MetricsClient(MetricsSink())).compare("kettle-1l")
        gc.collect()
    first = str(caught[0].message).splitlines()
    print(f"RuntimeWarning: {first[0]}")
    created = re.findall(r'File "([^"]+)", line (\d+), in (\w+)', str(caught[0].message))
    file, line, func = created[-1]
    print(f"  {first[1]}: ... {Path(file).name}:{line} in {func}")


async def never_retrieved():
    heard = []
    asyncio.get_running_loop().set_exception_handler(lambda _loop, ctx: heard.append(ctx))
    metrics = MetricsClient(MetricsSink(down=True))
    await metrics.record("seller-e", "timed out")
    trap3.Gateway(metrics).start_bare()  # create_task(), no reference kept
    await asyncio.sleep(0.2)
    gc.collect()
    for ctx in heard:
        print(f"asyncio: {ctx['message']}; created at {where(ctx['source_traceback'])}")


async def main():
    with running_sellers() as ports:
        print("-- trap 2: seller-e's sync SDK called on the loop --")
        await slow_step(ports)
        print("-- trap 1: a coroutine that was never awaited --")
        await never_awaited(ports)
    print("-- trap 3: a background Task that failed, never read --")
    await never_retrieved()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
