"""What gateway v10 adds to see itself: a histogram, a loop-lag monitor, JSON log lines, a task dump.

Everything here uses public asyncio APIs only, and reads time from the running loop's clock, so
it works the same on asyncio's loop, on uvloop and on the virtual clock the tests use.
"""

import asyncio
import json
import logging
import sys

from request_log import request_id
from spawn import spawn

BOUNDS_MS = (50, 100, 250, 500, 1000, 2500, float("inf"))  # about x2 apart, the 250 ms budget one of them


class Histogram:
    """Counts of values at or under each bound, plus their count and sum: enough for rates and tails."""

    def __init__(self, bounds=BOUNDS_MS):
        self.bounds = bounds
        self.buckets = [0] * len(bounds)
        self.count, self.sum = 0, 0.0

    def observe(self, value):
        self.count += 1
        self.sum += value
        for i, bound in enumerate(self.bounds):
            if value <= bound:
                self.buckets[i] += 1
                return

    def mean(self):
        return self.sum / self.count if self.count else 0.0

    def quantile(self, q):
        """The smallest bound with at least q of the values at or under it: an upper estimate."""
        if not self.count:
            return 0.0
        seen = 0
        for bound, n in zip(self.bounds, self.buckets, strict=True):
            seen += n
            if seen >= q * self.count:
                return bound
        return self.bounds[-1]

    def at_or_under(self, bound):
        """How many values were at or under `bound` (one of the bounds)."""
        return sum(n for b, n in zip(self.bounds, self.buckets, strict=True) if b <= bound)


class LagMonitor:
    """Loop lag as a metric: every `every` seconds, how late did a timer fire? Part 2's probe, kept on."""

    def __init__(self, every=0.05):
        self.every = every
        self.histogram = Histogram()
        self.worst_ms = 0.0  # the largest lag since the last take_worst()
        self.task = None

    def start(self):
        self.task = spawn(self._run(), name="loop-lag")

    async def stop(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.wait([self.task])

    async def _run(self):
        loop = asyncio.get_running_loop()
        while True:
            expected = loop.time() + self.every
            await asyncio.sleep(self.every)
            lag_ms = max(0.0, (loop.time() - expected) * 1000)
            self.histogram.observe(lag_ms)
            self.worst_ms = max(self.worst_ms, lag_ms)

    def take_worst(self):
        """The worst lag since the last call: what a scrape every few seconds would report as a gauge."""
        worst, self.worst_ms = self.worst_ms, 0.0
        return worst


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Values are escaped by json.dumps, so a newline in a value stays inside it."""

    def format(self, record):
        line = {
            "at_ms": getattr(record, "at_ms", None),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": request_id.get(),  # read in the context the log call ran in (Part 7)
        }
        line.update(getattr(record, "fields", {}))
        return json.dumps(line, separators=(",", ":"))


class LoopTime(logging.Filter):
    """Stamp each record with the running loop's clock, in ms since `start`: exact under a virtual clock."""

    def __init__(self, start=0.0):
        super().__init__()
        self.start = start

    def filter(self, record):
        try:
            record.at_ms = round((asyncio.get_running_loop().time() - self.start) * 1000)
        except RuntimeError:  # no running loop: a log call from a plain thread
            record.at_ms = None
        return True


class JsonLines(logging.Handler):
    """Keeps formatted JSON lines in a list, for programs and tests (production writes them to stdout)."""

    def __init__(self, start=0.0):
        super().__init__()
        self.lines = []
        self.addFilter(LoopTime(start))
        self.setFormatter(JsonFormatter())

    def emit(self, record):
        self.lines.append(self.format(record))

    def events(self):
        return [json.loads(line) for line in self.lines]


def json_lines(*names, start=0.0):
    """Send INFO and above from the named loggers to one JsonLines handler and return it."""
    handler = JsonLines(start)
    for name in names:
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return handler


def fields(**values):
    """extra= for a log call: these keys appear in the JSON line next to the standard ones."""
    return {"fields": values}


def dump_tasks(file=sys.stdout):
    """Every Task on this loop, with where it is waiting. Call it from a loop callback, e.g. on SIGUSR1."""
    tasks = sorted(asyncio.all_tasks(), key=lambda t: t.get_name())
    print(f"{len(tasks)} tasks", file=file)
    for task in tasks:
        try:  # 3.14+: the whole await chain, and who awaits it
            print(asyncio.format_call_graph(task), file=file)
            continue
        except AttributeError:  # no call graph (3.11 to 3.13), or the 3.14.0 to 3.14.7 bug on a stale awaiter
            pass
        print(
            f"* {task.get_name()} (one frame)", file=file
        )  # the Task's own coroutine, where it is suspended
        task.print_stack(file=file)
